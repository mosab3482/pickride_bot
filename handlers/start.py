from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ConversationHandler
)

import database as db
from config import ADMIN_IDS, RIDERS_GROUP_ID
from utils.lang import t, get_lang

# ── Conversation states ────────────────────────────────────────────────────────
CHOOSING_ROLE = 1


async def main_keyboard(user_id: int, lang: str = "en") -> ReplyKeyboardMarkup:
    """Build the main reply keyboard in the user's language."""
    buttons = [
        [KeyboardButton(t("btn_request_ride", lang)), KeyboardButton(t("btn_im_driver", lang))],
        [KeyboardButton(t("btn_update_location", lang)), KeyboardButton(t("btn_cancel_ride", lang))],
        [KeyboardButton(t("btn_help", lang)), KeyboardButton(t("btn_language", lang))],
    ]
    show_admin = user_id in ADMIN_IDS
    if not show_admin:
        show_admin = await db.is_db_admin(user_id)
    if show_admin:
        buttons.append([KeyboardButton(t("btn_admin", lang))])
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


# ─────────────────────────────────────────────
#  /start  — show language picker first
# ─────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = await db.get_user(user.id)
    await db.upsert_user(user.id, user.username or "", user.first_name or "")

    if not existing:
        await _notify_new_rider(context.bot, user)

    # Always show language picker on /start so user can change it anytime
    await update.message.reply_text(
        t("lang_choose", "en") + "\n" + t("lang_choose", "si"),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en"),
                InlineKeyboardButton("🇱🇰 සිංහල",   callback_data="setlang_si"),
            ]
        ]),
    )


# ─────────────────────────────────────────────
#  Language selection callback
# ─────────────────────────────────────────────
async def handle_set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.split("_")[1]   # "en" or "si"
    user = update.effective_user

    await db.set_user_language(user.id, lang)
    context.user_data["lang"] = lang

    # Confirm + show main menu
    await query.edit_message_text(t("lang_set", lang), parse_mode="Markdown")
    await query.message.reply_text(
        t("welcome", lang),
        parse_mode="Markdown",
        reply_markup=await main_keyboard(user.id, lang),
    )


# ─────────────────────────────────────────────
#  🌐 Language button on main keyboard
# ─────────────────────────────────────────────
async def handle_language_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        t("lang_choose", "en") + "\n" + t("lang_choose", "si"),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en"),
                InlineKeyboardButton("🇱🇰 සිංහල",   callback_data="setlang_si"),
            ]
        ]),
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    await update.message.reply_text(
        t("help_text", lang),
        parse_mode="Markdown",
        reply_markup=await main_keyboard(update.effective_user.id, lang),
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    context.user_data.clear()
    await update.message.reply_text(
        t("action_cancelled", lang),
        reply_markup=await main_keyboard(update.effective_user.id, lang),
    )
    return ConversationHandler.END


async def cmd_cancel_ride(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_lang(user.id)
    ride = await db.get_active_ride_for_rider(user.id)
    if not ride:
        ride = await db.get_active_ride_for_driver(user.id)

    if not ride:
        await update.message.reply_text("⚠️ No active ride found.")
        return

    await db.cancel_ride(ride["ride_id"])

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
            rider_lang = await get_lang(ride["rider_id"])
            await bot.send_message(
                ride["rider_id"],
                f"❌ Driver cancelled Ride #{ride['ride_id']}."
            )
        except Exception:
            pass

    await update.message.reply_text(
        t("ride_cancelled_rider", lang),
        reply_markup=await main_keyboard(user.id, lang),
    )


async def cmd_regis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset driver registration."""
    user = update.effective_user
    lang = await get_lang(user.id)
    context.user_data.clear()
    await update.message.reply_text(
        "🔄 Registration reset! Please choose your role below:",
        reply_markup=await main_keyboard(user.id, lang),
    )
