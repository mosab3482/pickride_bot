import logging
import asyncio
import traceback

from telegram import Update, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
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
    cmd_start, handle_help, cmd_cancel, cmd_cancel_ride,
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
    cmd_admin_help, cmd_status, cmd_rates,
    cmd_setbase, cmd_setrate, cmd_basekm, cmd_setradius,
    cmd_blockcat, cmd_unblockcat,
    cmd_block_user, cmd_unblock_user,
    cmd_drivers, cmd_riders, cmd_users,
    cmd_trips, cmd_revenue,
    cmd_groupid, cmd_whoami, cmd_session, cmd_restart,
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

    # ── Commands visible to ALL users ─────────────────
    user_commands = [
        BotCommand("start",      "Return to main menu"),
        BotCommand("regis",      "Reset driver registration"),
        BotCommand("cancel",     "Cancel current action"),
        BotCommand("cancelride", "Cancel active ride"),
    ]

    # ── Commands visible ONLY to admins ───────────────
    admin_commands = user_commands + [
        BotCommand("help",       "Show all admin commands"),
        BotCommand("status",     "Bot status"),
        BotCommand("rates",      "View all rates"),
        BotCommand("setbase",    "Set base fare (e.g. /setbase car 300)"),
        BotCommand("setrate",    "Set per-km rate (e.g. /setrate car 100)"),
        BotCommand("basekm",     "Set base km (e.g. /basekm 3)"),
        BotCommand("setradius",  "Set driver radius (e.g. /setradius 10)"),
        BotCommand("blockcat",   "Disable category (e.g. /blockcat bike)"),
        BotCommand("unblockcat", "Enable category (e.g. /unblockcat bike)"),
        BotCommand("block",      "Block user (e.g. /block 123456)"),
        BotCommand("unblock",    "Unblock user (e.g. /unblock 123456)"),
        BotCommand("drivers",    "List registered drivers"),
        BotCommand("riders",     "List registered riders"),
        BotCommand("users",      "All registered users"),
        BotCommand("trips",      "Trip statistics"),
        BotCommand("revenue",    "Revenue summary"),
        BotCommand("groupid",    "Get chat/group ID"),
        BotCommand("whoami",     "Show your sender info"),
        BotCommand("session",    "Current session settings"),
        BotCommand("restart",    "Restart bot session"),
    ]

    for attempt in range(1, 4):
        try:
            # Set basic commands for everyone
            await app.bot.set_my_commands(
                user_commands,
                scope=BotCommandScopeDefault(),
            )

            # Collect all admin IDs (env + DB)
            from config import ADMIN_IDS
            db_admins = await db.get_all_admins()
            all_admin_ids = set(ADMIN_IDS) | {a["user_id"] for a in db_admins}

            # Set full admin commands per admin (private chat scope)
            for admin_id in all_admin_ids:
                try:
                    await app.bot.set_my_commands(
                        admin_commands,
                        scope=BotCommandScopeChat(chat_id=admin_id),
                    )
                except Exception as e:
                    logger.warning(f"Could not set admin commands for {admin_id}: {e}")

            logger.info(
                f"Commands set: {len(user_commands)} public, "
                f"{len(admin_commands)} admin (for {len(all_admin_ids)} admin(s))"
            )
            break
        except NetworkError as e:
            logger.warning(f"set_my_commands attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                await asyncio.sleep(2)

    logger.info("TeleCabs Bot is ready.")


async def post_shutdown(app: Application):
    logger.info("Shutting down TeleCabs Bot...")
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
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("cancel",      cmd_cancel))
    app.add_handler(CommandHandler("cancelride",  cmd_cancel_ride))
    # NOTE: /regis is handled inside driver_conv_handler() as an entry_point

    # ── Admin Slash Commands ──────────────────────
    app.add_handler(CommandHandler("help",        cmd_admin_help))
    app.add_handler(CommandHandler("status",      cmd_status))
    app.add_handler(CommandHandler("rates",       cmd_rates))
    app.add_handler(CommandHandler("setbase",     cmd_setbase))
    app.add_handler(CommandHandler("setrate",     cmd_setrate))
    app.add_handler(CommandHandler("basekm",      cmd_basekm))
    app.add_handler(CommandHandler("setradius",   cmd_setradius))
    app.add_handler(CommandHandler("blockcat",    cmd_blockcat))
    app.add_handler(CommandHandler("unblockcat",  cmd_unblockcat))
    app.add_handler(CommandHandler("block",       cmd_block_user))
    app.add_handler(CommandHandler("unblock",     cmd_unblock_user))
    app.add_handler(CommandHandler("drivers",     cmd_drivers))
    app.add_handler(CommandHandler("riders",      cmd_riders))
    app.add_handler(CommandHandler("users",       cmd_users))
    app.add_handler(CommandHandler("trips",       cmd_trips))
    app.add_handler(CommandHandler("revenue",     cmd_revenue))
    app.add_handler(CommandHandler("groupid",     cmd_groupid))
    app.add_handler(CommandHandler("whoami",      cmd_whoami))
    app.add_handler(CommandHandler("session",     cmd_session))
    app.add_handler(CommandHandler("restart",     cmd_restart))

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
    app.add_handler(MessageHandler(filters.Regex("^🔴 End Trip$"), handle_end_trip))

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

    logger.info("Starting TeleCabs Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
