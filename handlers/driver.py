from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)

import database as db
from handlers.start import main_keyboard, cmd_cancel

# ── Conversation states ───────────────────────────────────────────────────────
(
    DRV_PHONE,
    DRV_VEHICLE,
    DRV_NAME,
    DRV_PLATE,
    DRV_LOCATION_INFO,
    DRV_LOCATION,
    DRV_DONE,
) = range(10, 17)


def driver_dashboard_keyboard(is_muted: bool) -> ReplyKeyboardMarkup:
    mute_btn = "🔔 Unmute (recommended)" if is_muted else "🔕 Mute"
    buttons = [
        [KeyboardButton("📍 Check-in", request_location=True)],
        [KeyboardButton(mute_btn)],
        [KeyboardButton("🔧 Settings")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def vehicle_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚗 Car",  callback_data="veh_car"),
         InlineKeyboardButton("🛺 Tuk",  callback_data="veh_tuk")],
        [InlineKeyboardButton("🏍️ Bike", callback_data="veh_bike"),
         InlineKeyboardButton("🚐 Van",  callback_data="veh_van")],
    ])


VEHICLE_LABELS = {
    "veh_car":  "🚗 Car",
    "veh_tuk":  "🛺 Tuk",
    "veh_bike": "🏍️ Bike",
    "veh_van":  "🚐 Van",
}
VEHICLE_KEYS = {
    "veh_car":  "car",
    "veh_tuk":  "tuk",
    "veh_bike": "bike",
    "veh_van":  "van",
}


# ─────────────────────────────────────────────
#  Entry point — "I'm a Driver" button
# ─────────────────────────────────────────────
async def driver_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    driver = await db.get_driver(user.id)

    if driver:
        # Already registered → show dashboard
        is_muted = driver["is_muted"]
        await update.message.reply_text(
            "👌 Welcome back, driver!\n\nPlease choose an action from menu below 👇",
            reply_markup=driver_dashboard_keyboard(is_muted),
        )
        return ConversationHandler.END

    # New driver → ask for phone
    phone_btn = KeyboardButton("📱 Send Number", request_contact=True)
    await update.message.reply_text(
        "Please send us your phone number. "
        "We do not share this number without permission.",
        reply_markup=ReplyKeyboardMarkup(
            [[phone_btn]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return DRV_PHONE


async def drv_receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone = contact.phone_number if contact else update.message.text
    context.user_data["drv_phone"] = phone
    await db.set_user_phone(update.effective_user.id, phone)

    await update.message.reply_text(
        "Select your Vehicle Type:",
        reply_markup=vehicle_inline_keyboard(),
    )
    return DRV_VEHICLE


async def drv_receive_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    veh_key  = query.data                    # e.g. "veh_car"
    veh_label = VEHICLE_LABELS[veh_key]      # e.g. "🚗 Car"
    veh_type  = VEHICLE_KEYS[veh_key]        # e.g. "car"
    context.user_data["drv_vehicle"] = veh_type

    await query.edit_message_text(
        f"👌 {veh_label} selected!\n\n👤 Please enter your full name:"
    )
    return DRV_NAME


async def drv_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["drv_name"] = name

    await update.message.reply_text(
        f"PickRide:\n👌 Name set: *{name}*\n\n🔢 Please enter your vehicle plate number:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return DRV_PLATE


async def drv_receive_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.strip()
    context.user_data["drv_plate"] = plate

    await update.message.reply_text(
        f"👌 Plate number set: *{plate}*\n\n"
        "Almost done. A few things to note: Telegram has no live GPS location support, "
        "so every time you change location you need to check-in. "
        "This will help us to find passengers around. Click \"Next\".",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("▶️ Next")]], resize_keyboard=True
        ),
    )
    return DRV_LOCATION_INFO


async def drv_location_info_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please share your current location (press the button) "
        "or type address, so passengers around can find you.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Send Location", request_location=True)]],
            resize_keyboard=True,
        ),
    )
    return DRV_LOCATION


async def drv_receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    if not loc:
        await update.message.reply_text("Please use the button to share your location.")
        return DRV_LOCATION

    user = update.effective_user
    context.user_data["drv_lat"] = loc.latitude
    context.user_data["drv_lon"] = loc.longitude

    # Save driver to DB
    await db.upsert_driver(
        user_id=user.id,
        full_name=context.user_data["drv_name"],
        plate=context.user_data["drv_plate"],
        vehicle_type=context.user_data["drv_vehicle"],
    )
    await db.update_driver_location(user.id, loc.latitude, loc.longitude)

    await update.message.reply_text(
        "We're all set! You'll be notified about passengers and orders nearby. "
        "Keep this app running. Click \"Next\".",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("▶️ Next")]], resize_keyboard=True
        ),
    )
    return DRV_DONE


async def drv_final_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = await db.get_driver(update.effective_user.id)
    is_muted = driver["is_muted"] if driver else False

    await update.message.reply_text(
        "Please choose an action from menu below 👇",
        reply_markup=driver_dashboard_keyboard(is_muted),
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Dashboard actions
# ─────────────────────────────────────────────
async def drv_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle location shared via Check-in button."""
    loc = update.message.location
    user = update.effective_user
    if loc:
        await db.update_driver_location(user.id, loc.latitude, loc.longitude)
        driver = await db.get_driver(user.id)
        is_muted = driver["is_muted"] if driver else False

        await update.message.reply_text(
            "👌 Thanks for checking-in! Check location above, if it's incorrect, "
            "check-in again and then tap on paperclip-location (instead of pressing a button)."
        )
        await update.message.reply_text(
            "Please choose an action from menu below 👇",
            reply_markup=driver_dashboard_keyboard(is_muted),
        )
    else:
        await update.message.reply_text("Please share your location using the button.")


async def drv_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.set_driver_mute(user.id, True)
    await update.message.reply_text(
        "⚠️ But keep in mind that you will NOT receive notifications "
        "about passengers around until you unmute yourself.",
        reply_markup=driver_dashboard_keyboard(is_muted=True),
    )
    await update.message.reply_text("Please choose an action from menu below 👇")


async def drv_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.set_driver_mute(user.id, False)
    await update.message.reply_text(
        "You're unmuted now and will receive notifications about passengers around you.",
        reply_markup=driver_dashboard_keyboard(is_muted=False),
    )
    await update.message.reply_text("Please choose an action from menu below 👇")


async def drv_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu from driver settings."""
    user = update.effective_user
    await update.message.reply_text(
        "Please choose an action from menu below 👇",
        reply_markup=await main_keyboard(user.id),
    )


async def drv_update_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 📍 Update My Location from main menu."""
    user = update.effective_user
    driver = await db.get_driver(user.id)
    if not driver:
        await update.message.reply_text("⚠️ You're not registered as a driver.")
        return

    await update.message.reply_text(
        "Please share your current location to update your position:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Send Location", request_location=True)]],
            resize_keyboard=True,
        ),
    )


# ─────────────────────────────────────────────
#  ConversationHandler builder
# ─────────────────────────────────────────────
def driver_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚗 I'm a Driver$"), driver_entry)],
        states={
            DRV_PHONE: [
                MessageHandler(filters.CONTACT, drv_receive_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, drv_receive_phone),
            ],
            DRV_VEHICLE: [CallbackQueryHandler(drv_receive_vehicle, pattern="^veh_")],
            DRV_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, drv_receive_name)],
            DRV_PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, drv_receive_plate)],
            DRV_LOCATION_INFO: [MessageHandler(filters.Regex("^▶️ Next$"), drv_location_info_next)],
            DRV_LOCATION: [MessageHandler(filters.LOCATION, drv_receive_location)],
            DRV_DONE: [MessageHandler(filters.Regex("^▶️ Next$"), drv_final_next)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )
