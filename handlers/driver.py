from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)

import database as db
from config import DRIVERS_GROUP_ID
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


# ── Updated vehicle types ─────────────────────────────────────────────────────
VEHICLE_LABELS = {
    "veh_bike":    "🏍️ Bike (1 Seat)",
    "veh_tuk":     "🛺 Tuk (2 Seats)",
    "veh_car":     "🚗 Car (3 Seats)",
    "veh_minivan": "🚙 Mini Van (5 Seats)",
    "veh_van":     "🚐 Van (10 Seats)",
    "veh_bus":     "🚌 Bus (25+ Seats)",
}
VEHICLE_KEYS = {
    "veh_bike":    "bike",
    "veh_tuk":     "tuk",
    "veh_car":     "car",
    "veh_minivan": "minivan",
    "veh_van":     "van",
    "veh_bus":     "bus",
}


def vehicle_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏍️ Bike (1 Seat)",    callback_data="veh_bike"),
         InlineKeyboardButton("🛺 Tuk (2 Seats)",    callback_data="veh_tuk")],
        [InlineKeyboardButton("🚗 Car (3 Seats)",    callback_data="veh_car"),
         InlineKeyboardButton("🚙 Mini Van (5 Seats)", callback_data="veh_minivan")],
        [InlineKeyboardButton("🚐 Van (10 Seats)",   callback_data="veh_van"),
         InlineKeyboardButton("🚌 Bus (25+ Seats)",  callback_data="veh_bus")],
    ])


def driver_dashboard_keyboard(is_muted: bool) -> ReplyKeyboardMarkup:
    mute_btn = "🔔 Unmute (recommended)" if is_muted else "🔕 Mute"
    return ReplyKeyboardMarkup([
        [KeyboardButton("📍 Check-in", request_location=True)],
        [KeyboardButton(mute_btn)],
        [KeyboardButton("🔧 Settings")],
    ], resize_keyboard=True)


# ─────────────────────────────────────────────
#  Entry point — "I'm a Driver" button
# ─────────────────────────────────────────────
async def driver_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    driver = await db.get_driver(user.id)

    if driver:
        is_muted = driver["is_muted"]
        await update.message.reply_text(
            "👌 Welcome back, driver!\n\nPlease choose an action from the menu below 👇",
            reply_markup=driver_dashboard_keyboard(is_muted),
        )
        return ConversationHandler.END

    # New driver → start registration
    return await _start_registration(update, context)


async def _start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear old data and restart registration from scratch."""
    context.user_data.clear()
    phone_btn = KeyboardButton("📱 Share My Number", request_contact=True)
    await update.message.reply_text(
        "🚗 Driver Registration\n\n"
        "We need a few details to register you as a TeleCabs driver.\n\n"
        "Step 1/5 — Share your phone number:",
        reply_markup=ReplyKeyboardMarkup(
            [[phone_btn]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return DRV_PHONE


# ─────────────────────────────────────────────
#  /regis command — full re-registration
# ─────────────────────────────────────────────
async def cmd_regis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /regis — Delete existing driver record and restart registration.
    Works as if it's the first time.
    """
    user = update.effective_user
    driver = await db.get_driver(user.id)

    if driver:
        # Delete driver record so they can re-register fresh
        await db.delete_driver(user.id)

    context.user_data.clear()
    await update.message.reply_text(
        "♻️ Your driver profile has been reset.\n\n"
        "Starting fresh registration...",
        reply_markup=ReplyKeyboardRemove(),
    )
    return await _start_registration(update, context)


# ─────────────────────────────────────────────
#  Registration steps
# ─────────────────────────────────────────────
async def drv_receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone = contact.phone_number if contact else update.message.text.strip()
    context.user_data["drv_phone"] = phone
    await db.set_user_phone(update.effective_user.id, phone)

    await update.message.reply_text(
        "✅ Phone saved!\n\nStep 2/5 — Select your vehicle type:",
        reply_markup=vehicle_inline_keyboard(),
    )
    return DRV_VEHICLE


async def drv_receive_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    veh_key   = query.data
    veh_label = VEHICLE_LABELS.get(veh_key, veh_key)
    veh_type  = VEHICLE_KEYS.get(veh_key, veh_key)
    context.user_data["drv_vehicle"] = veh_type

    await query.edit_message_text(
        f"✅ {veh_label} selected!\n\nStep 3/5 — Please enter your full name:"
    )
    return DRV_NAME


async def drv_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["drv_name"] = name

    await update.message.reply_text(
        f"✅ Name: {name}\n\n"
        f"Step 4/5 — Enter vehicle number & model\n"
        f"(e.g. CAB-1234, Prius)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return DRV_PLATE


async def drv_receive_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.strip().upper()
    context.user_data["drv_plate"] = plate

    # Extract plate and model from input like "CAZ 6560 WagonR"
    parts = plate.split()
    if len(parts) >= 3:
        plate_num = " ".join(parts[:2])
        model     = " ".join(parts[2:])
        plate_display = f"{plate_num} • {model}"
    else:
        plate_display = plate

    await update.message.reply_text(
        f"✅ {plate_display}\n\n"
        "Step 5/5 — Share your location 📍\n"
        "Check-in when you move\n\n"
        "Tap Next ➡️",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("▶️ Next")]], resize_keyboard=True
        ),
    )
    return DRV_LOCATION_INFO


async def drv_location_info_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📍 Please share your current location:",
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

    await db.upsert_driver(
        user_id=user.id,
        full_name=context.user_data["drv_name"],
        plate=context.user_data["drv_plate"],
        vehicle_type=context.user_data["drv_vehicle"],
    )
    await db.update_driver_location(user.id, loc.latitude, loc.longitude)

    # Notify DRIVERS group about new registration
    async def _send_to_drivers_group():
        if not DRIVERS_GROUP_ID:
            return
        try:
            drv_user = await db.get_user(user.id)
            username_str = f"@{drv_user['username']}" if drv_user and drv_user["username"] else user.first_name
            phone = drv_user["phone"] if drv_user and drv_user.get("phone") else "N/A"
            plate = context.user_data.get("drv_plate", "N/A")
            vtype = context.user_data.get("drv_vehicle", "N/A")
            name  = context.user_data.get("drv_name", "N/A")
            msg = (
                f"🚗 *New Driver Registered*\n\n"
                f"👤 Name: {name}\n"
                f"🔗 Username: {username_str}\n"
                f"📞 Phone: {phone}\n"
                f"🚘 Vehicle: {vtype.title()}\n"
                f"🔢 Plate: {plate}\n"
                f"🆔 ID: `{user.id}`"
            )
            await context.bot.send_message(DRIVERS_GROUP_ID, msg, parse_mode="Markdown")
        except Exception:
            pass
    await _send_to_drivers_group()

    await update.message.reply_text(
        "✅ Registration complete!\n\n"
        "You'll get ride requests nearby\n"
        "Keep app active & update location 📍\n\n"
        "Tap Next ➡️",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("▶️ Next")]], resize_keyboard=True
        ),
    )
    return DRV_DONE


async def drv_final_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = await db.get_driver(update.effective_user.id)
    is_muted = driver["is_muted"] if driver else False
    await update.message.reply_text(
        "🚗 Driver Dashboard — Choose an action 👇",
        reply_markup=driver_dashboard_keyboard(is_muted),
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Dashboard actions
# ─────────────────────────────────────────────
async def drv_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    user = update.effective_user
    if loc:
        await db.update_driver_location(user.id, loc.latitude, loc.longitude)
        driver = await db.get_driver(user.id)
        is_muted = driver["is_muted"] if driver else False
        await update.message.reply_text(
            "👌 Location updated\n\n"
            "If wrong, check-in again or send via 📎 Location"
        )
        await update.message.reply_text(
            "Driver Dashboard 👇",
            reply_markup=driver_dashboard_keyboard(is_muted),
        )
    else:
        await update.message.reply_text("Please share your location using the button.")


async def drv_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db.set_driver_mute(update.effective_user.id, True)
    await update.message.reply_text(
        "🔕 Muted. You will NOT receive ride notifications until you unmute.",
        reply_markup=driver_dashboard_keyboard(is_muted=True),
    )


async def drv_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db.set_driver_mute(update.effective_user.id, False)
    await update.message.reply_text(
        "🔔 Unmuted! You will now receive nearby ride requests.",
        reply_markup=driver_dashboard_keyboard(is_muted=False),
    )


async def drv_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        "Main menu 👇",
        reply_markup=await main_keyboard(user.id),
    )


async def drv_update_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    driver = await db.get_driver(user.id)
    if not driver:
        await update.message.reply_text("⚠️ You're not registered as a driver.")
        return
    await update.message.reply_text(
        "Share your current location to update your position:",
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
        entry_points=[
            MessageHandler(filters.Regex("^🚗 I'm a Driver$"), driver_entry),
            CommandHandler("regis", cmd_regis),
        ],
        states={
            DRV_PHONE: [
                MessageHandler(filters.CONTACT, drv_receive_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, drv_receive_phone),
            ],
            DRV_VEHICLE: [CallbackQueryHandler(drv_receive_vehicle, pattern="^veh_")],
            DRV_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, drv_receive_name)],
            DRV_PLATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, drv_receive_plate)],
            DRV_LOCATION_INFO: [MessageHandler(filters.Regex("^▶️ Next$"), drv_location_info_next)],
            DRV_LOCATION:      [MessageHandler(filters.LOCATION, drv_receive_location)],
            DRV_DONE:          [MessageHandler(filters.Regex("^▶️ Next$"), drv_final_next)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )
