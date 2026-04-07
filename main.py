import logging
import asyncio
import signal

from telegram.error import NetworkError

from telegram import Update, BotCommand
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
from handlers.rider import rider_conv_handler
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
#  Boot
# ─────────────────────────────────────────────
async def post_init(app: Application):
    await db.init_db()
    # Clean expired route cache on startup
    await db.cleanup_expired_cache()
    # Retry set_my_commands up to 3 times (transient network errors)
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
            if attempt == 3:
                logger.error("Could not set bot commands after 3 attempts, continuing anyway...")
            else:
                await asyncio.sleep(2)
    logger.info("PickRide Bot is ready.")


async def post_shutdown(app: Application):
    """Graceful shutdown — close database pool."""
    logger.info("Shutting down PickRide Bot...")
    await db.close_pool()
    logger.info("Database pool closed.")


# ─────────────────────────────────────────────
#  Trip end text router (meter input + waiting)
# ─────────────────────────────────────────────
async def _trip_end_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Route text messages for the trip end flow:
    1. If driver is entering meter distance → handle_meter_distance
    2. If driver is entering waiting time → handle_waiting_time
    3. If admin is awaiting input → admin_text_input
    4. Otherwise → ignore
    """
    # Step 1: Check if driver is entering meter distance
    if context.user_data.get("ending_ride"):
        handled = await handle_meter_distance(update, context)
        if handled:
            return

    # Step 2: Check if driver is entering waiting time
    if context.user_data.get("awaiting_waiting"):
        handled = await handle_waiting_time(update, context)
        if handled:
            return

    # Step 3: Admin text input (only if admin is awaiting)
    await admin_text_input(update, context)


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

    # ── Commands ─────────────────────────────────
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("cancel",     cmd_cancel))
    app.add_handler(CommandHandler("cancelride", cmd_cancel_ride))
    app.add_handler(CommandHandler("regis",      cmd_regis))

    # ── Conversation handlers (order matters!) ───
    app.add_handler(driver_conv_handler())   # Driver registration FSM
    app.add_handler(rider_conv_handler())    # Rider request FSM

    # ── Callback queries ─────────────────────────
    app.add_handler(CallbackQueryHandler(accept_ride_callback,   pattern=r"^accept_\d+$"))
    app.add_handler(CallbackQueryHandler(start_trip_callback,    pattern=r"^starttrip_\d+$"))
    app.add_handler(CallbackQueryHandler(share_location_callback,pattern=r"^shareloc_\d+$"))
    app.add_handler(CallbackQueryHandler(rating_callback,        pattern=r"^rate_\d+_\d+$"))

    # ── Admin callbacks ──────────────────────────
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^adm_"))

    # ── Main menu text buttons ───────────────────
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Help$"),                handle_help))
    app.add_handler(MessageHandler(filters.Regex("^👑 Admin Control ⚙️$"),    admin_entry))
    app.add_handler(MessageHandler(filters.Regex("^🟥 Cancel Current Ride$"), cmd_cancel_ride))
    app.add_handler(MessageHandler(filters.Regex("^📍 Update My Location$"),  drv_update_location))

    # ── Driver dashboard buttons ─────────────────
    app.add_handler(MessageHandler(filters.Regex("^🔕 Mute$"),                drv_mute))
    app.add_handler(MessageHandler(filters.Regex("^🔔 Unmute"),               drv_unmute))
    app.add_handler(MessageHandler(filters.Regex("^🔧 Settings$"),            drv_settings))
    app.add_handler(MessageHandler(filters.Regex("^🟩 End Trip$"),            handle_end_trip))

    # ── Location messages ────────────────────────
    # Priority: trip start location → live update → driver check-in
    app.add_handler(MessageHandler(
        filters.LOCATION & ~filters.UpdateType.EDITED_MESSAGE,
        _location_router,
    ))

    # ── Text input router (trip end + admin) ─────
    # This MUST be last — catches all non-command text
    # Routes to: meter input → waiting time → admin input
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        _trip_end_text_router,
    ))

    logger.info("Starting PickRide Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


async def _location_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route location messages to the correct handler based on context."""
    # 1. Check if driver is in "starting_ride" state
    if context.user_data.get("starting_ride"):
        await handle_start_trip_location(update, context)
        return

    # 2. Check if driver has active in_progress trip → live tracking
    user_id = update.effective_user.id
    active = await db.get_active_ride_for_driver(user_id)
    if active and active["status"] == "in_progress":
        await live_location_update(update, context)
        return

    # 3. Driver check-in (dashboard)
    driver = await db.get_driver(user_id)
    if driver:
        await drv_checkin(update, context)


if __name__ == "__main__":
    main()
