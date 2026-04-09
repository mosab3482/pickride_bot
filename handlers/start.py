from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler

import database as db
from config import ADMIN_IDS, RIDERS_GROUP_ID

# ── Conversation states ────────────────────────────────────────────────────────
CHOOSING_ROLE = 1


async def main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Build the main reply keyboard. Shows Admin button for admins (env + DB)."""
    buttons = [
        [KeyboardButton("🚕 Request Ride"), KeyboardButton("🚗 I'm a Driver")],
        [KeyboardButton("📍 Update My Location"), KeyboardButton("🟥 Cancel Current Ride")],
        [KeyboardButton("ℹ️ Help")],
    ]
    # Check both .env admins and DB admins
    show_admin = user_id in ADMIN_IDS
    if not show_admin:
        show_admin = await db.is_db_admin(user_id)
    if show_admin:
        buttons.append([KeyboardButton("👑 Admin Control ⚙️")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def _notify_new_rider(bot, user):
    """Send new rider registration notice to RIDERS group."""
    if not RIDERS_GROUP_ID:
        return
    try:
        username_str = f"@{user.username}" if user.username else user.first_name
        msg = (
            f"🚶 *New Rider Registered*\n\n"
            f"👤 Name: {user.full_name}\n"
            f"🔗 Username: {username_str}\n"
            f"🆔 ID: `{user.id}`"
        )
        await bot.send_message(RIDERS_GROUP_ID, msg, parse_mode="Markdown")
    except Exception:
        pass


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = await db.get_user(user.id)
    await db.upsert_user(user.id, user.username or "", user.first_name or "")

    # Notify riders group only on first registration (new user)
    if not existing:
        await _notify_new_rider(context.bot, user)

    await update.message.reply_text(
        "👋 *Welcome to TeleCabs 🚕*\n\nFast and simple taxi service.",
        parse_mode="Markdown",
        reply_markup=await main_keyboard(user.id),
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "TeleCabs — Help\n\n"
        "🚕 *Request Ride* — Book a taxi\n"
        "🚗 *I'm a Driver* — Register or go online as driver\n"
        "📍 *Update My Location* — Update your GPS position\n"
        "🟥 *Cancel Current Ride* — Cancel active booking\n\n"
        "*Commands:*\n"
        "/start — Return to main menu\n"
        "/cancel — Cancel current action\n"
        "/cancelride — Cancel active ride",
        parse_mode="Markdown",
        reply_markup=await main_keyboard(update.effective_user.id),
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Action cancelled.",
        reply_markup=await main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


async def cmd_cancel_ride(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ride = await db.get_active_ride_for_rider(user.id)
    if not ride:
        ride = await db.get_active_ride_for_driver(user.id)

    if not ride:
        await update.message.reply_text("⚠️ No active ride found.")
        return

    await db.cancel_ride(ride["ride_id"])

    # Notify the other party
    bot = context.bot
    if ride["rider_id"] == user.id and ride["driver_id"]:
        try:
            await bot.send_message(
                ride["driver_id"],
                f"❌ Rider cancelled Ride #{ride['ride_id']}."
            )
        except Exception:
            pass
    elif ride["driver_id"] == user.id and ride["rider_id"]:
        try:
            await bot.send_message(
                ride["rider_id"],
                f"❌ Driver cancelled Ride #{ride['ride_id']}."
            )
        except Exception:
            pass

    await update.message.reply_text(
        "❌ Ride request cancelled.",
        reply_markup=await main_keyboard(user.id),
    )


async def cmd_regis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset driver registration."""
    user = update.effective_user
    context.user_data.clear()
    await update.message.reply_text(
        "🔄 Registration reset! Please choose your role below:",
        reply_markup=await main_keyboard(user.id),
    )
