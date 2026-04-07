import logging
import asyncio
import traceback

from telegram import Update, BotCommand
from telegram.error import NetworkError, TelegramError
from telegram.ext import (
    Application, ApplicationBuilder,
    CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

import database as db
from config import BOT_TOKEN

# ── Handlers ──────────────────────────────────────────────────────────────────
from handlers.start import (
    cmd_start, handle_help, cmd_cancel, cmd_cancel_ride, cmd_regis,
    main_keyboard,
)
from handlers.driver import (
    driver_conv_handler,
    drv_checkin, drv_mute, drv_unmute, drv_settings, drv_update_location,
)
from handlers.rider import rider_conv_handler, rider_confirm
from handlers.trip import (
    accept_ride_callback,
    start_trip_callback,
    share_location_callback,
    handle_start_trip_location,
    handle_end_trip,
    handle_meter_distance,
    handle_waiting_time,
    live_location_update,
    rating_callback,
)
from handlers.admin import (
    admin_entry, admin_callback, admin_text_input,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Global Error Handler — surfaces silent crashes
# ─────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and notify user when possible."""
    err = context.error
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    logger.error(f"Exception while handling update:\n{tb}")

    # Try to reply to the user so they know something went wrong
    if isinstance(update, Update):
        msg = None
        if update.callback_query:
            try:
                await update.callback_query.answer("An error occurred. Please try again.")
            except Exception:
                pass
            msg = update.callback_query.message
        elif update.message:
            msg = update.message

        if msg:
            try:
                await msg.reply_text(
                    "Something went wrong. Please try again or use /start to restart."
                )
            except Exception:
                pass


# ─────────────────────────────────────────────
#  Boot
# ─────────────────────────────────────────────
async def post_init(app: Application):
    await db.init_db()
    await db.cleanup_expired_cache()
    for attempt in range(1, 4):
        try:
            await app.bot.set_my_commands([
                BotCommand("start",      "Return to main menu"),
                BotCommand("regis",      "Reset driver registration"),
                BotCommand("cancel",     "Cancel current action"),
                BotCommand("cancelride", "Cancel active ride"),
            ])
            break
        except NetworkError as e:
            logger.warning(f"set_my_commands attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                await asyncio.sleep(2)
    logger.info("PickRide Bot is ready.")


async def post_shutdown(app: Application):
    logger.info("Shutting down PickRide Bot...")
    await db.close_pool()
    logger.info("Database pool closed.")


# ─────────────────────────────────────────────
#  Trip end text router
# ─────────────────────────────────────────────
async def _trip_end_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("ending_ride"):
        handled = await handle_meter_distance(update, context)
        if handled:
            return

    if context.user_data.get("awaiting_waiting"):
        handled = await handle_waiting_time(update, context)
        if handled:
            return

    await admin_text_input(update, context)


# ─────────────────────────────────────────────
#  Location router
# ─────────────────────────────────────────────
async def _location_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("starting_ride"):
        await handle_start_trip_location(update, context)
        return

    user_id = update.effective_user.id
    active = await db.get_active_ride_for_driver(user_id)
    if active and active["status"] == "in_progress":
        await live_location_update(update, context)
        return

    driver = await db.get_driver(user_id)
    if driver:
        await drv_checkin(update, context)


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Please configure your .env file.")
        return

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # ── Global error handler ─────────────────────
    app.add_error_handler(error_handler)

    # ── Commands ─────────────────────────────────
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("cancel",     cmd_cancel))
    app.add_handler(CommandHandler("cancelride", cmd_cancel_ride))
    app.add_handler(CommandHandler("regis",      cmd_regis))

    # ── Conversation handlers ─────────────────────
    # Group 0: ConversationHandlers - highest priority for active conversations
    app.add_handler(driver_conv_handler(), group=0)
    app.add_handler(rider_conv_handler(),  group=0)

    # ── ride_confirm fallback in Group 0 AFTER conv handlers ─────────────────
    # When ConversationHandler has RIDER_CONFIRM state active, it intercepts first.
    # When state is lost (bot restart), this global handler catches it.
    app.add_handler(
        CallbackQueryHandler(rider_confirm, pattern=r"^ride_(confirm|cancel)$"),
        group=0
    )

    # ── All other callback queries in Group 1 ────
    app.add_handler(CallbackQueryHandler(accept_ride_callback,    pattern=r"^accept_\d+$"),  group=1)
    app.add_handler(CallbackQueryHandler(start_trip_callback,     pattern=r"^starttrip_\d+$"), group=1)
    app.add_handler(CallbackQueryHandler(share_location_callback, pattern=r"^shareloc_\d+$"), group=1)
    app.add_handler(CallbackQueryHandler(rating_callback,         pattern=r"^rate_\d+_\d+$"), group=1)
    app.add_handler(CallbackQueryHandler(admin_callback,          pattern=r"^adm_"),          group=1)

    # ── Main menu text buttons ───────────────────
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Help$"),                handle_help))
    app.add_handler(MessageHandler(filters.Regex("^👑 Admin Control ⚙️$"),    admin_entry))
    app.add_handler(MessageHandler(filters.Regex("^🟥 Cancel Current Ride$"), cmd_cancel_ride))
    app.add_handler(MessageHandler(filters.Regex("^📍 Update My Location$"),  drv_update_location))

    # ── Driver dashboard buttons ─────────────────
    app.add_handler(MessageHandler(filters.Regex("^🔕 Mute$"),   drv_mute))
    app.add_handler(MessageHandler(filters.Regex("^🔔 Unmute"),  drv_unmute))
    app.add_handler(MessageHandler(filters.Regex("^🔧 Settings$"), drv_settings))
    app.add_handler(MessageHandler(filters.Regex("^🟩 End Trip$"), handle_end_trip))

    # ── Location messages ────────────────────────
    app.add_handler(MessageHandler(
        filters.LOCATION & ~filters.UpdateType.EDITED_MESSAGE,
        _location_router,
    ))

    # ── Text input router ────────────────────────
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        _trip_end_text_router,
    ))

    logger.info("Starting PickRide Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
