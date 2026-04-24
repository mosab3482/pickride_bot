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
from utils.lang import t, get_lang

# ── Conversation states ───────────────────────────────────────────────────────
(
    DRV_PHONE,
    DRV_VEHICLE,
    DRV_NAME,
    DRV_PLATE,
    DRV_RATE,
    DRV_LOCATION_INFO,
    DRV_LOCATION,
    DRV_DONE,
) = range(10, 18)


# ── Vehicle type label-keys → lang.py translation keys ───────────────────────
# The human-readable label is resolved via t(key, lang) so Sinhala users see
# their own language name during registration.
VEHICLE_LABEL_KEYS = {
    "veh_bike":    "veh_bike",
    "veh_tuk":     "veh_tuk",
    "veh_car":     "veh_car",
    "veh_minivan": "veh_minivan",
    "veh_van":     "veh_van",
    "veh_bus":     "veh_bus",
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
        [KeyboardButton(mute_btn), KeyboardButton("💰 My Rate")],
        [KeyboardButton("🔧 Settings")],
    ], resize_keyboard=True)


# ─────────────────────────────────────────────
#  Entry point — "I'm a Driver" button
# ─────────────────────────────────────────────
async def driver_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_lang(user.id)
    driver = await db.get_driver(user.id)

    if driver:
        is_muted = driver["is_muted"]
        await update.message.reply_text(
            t("drv_welcome_back", lang),
            reply_markup=driver_dashboard_keyboard(is_muted),
        )
        return ConversationHandler.END

    return await _start_registration(update, context)


async def _start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear old data and restart registration from scratch."""
    lang = await get_lang(update.effective_user.id)
    context.user_data.clear()
    phone_btn = KeyboardButton("📱 Share My Number", request_contact=True)
    await update.message.reply_text(
        t("drv_reg_start", lang),
        reply_markup=ReplyKeyboardMarkup(
            [[phone_btn]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return DRV_PHONE


# ─────────────────────────────────────────────
#  /regis command — full re-registration
# ─────────────────────────────────────────────
async def cmd_regis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_lang(user.id)
    driver = await db.get_driver(user.id)
    if driver:
        await db.delete_driver(user.id)
    context.user_data.clear()
    await update.message.reply_text(t("drv_reset", lang), reply_markup=ReplyKeyboardRemove())
    return await _start_registration(update, context)


# ─────────────────────────────────────────────
#  Registration steps
# ─────────────────────────────────────────────
async def drv_receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    contact = update.message.contact
    phone = contact.phone_number if contact else update.message.text.strip()
    context.user_data["drv_phone"] = phone
    await db.set_user_phone(update.effective_user.id, phone)
    await update.message.reply_text(
        t("drv_phone_saved", lang),
        reply_markup=vehicle_inline_keyboard(),
    )
    return DRV_VEHICLE


async def drv_receive_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = await get_lang(query.from_user.id)

    veh_key   = query.data
    label_key = VEHICLE_LABEL_KEYS.get(veh_key, veh_key)
    veh_label = t(label_key, lang)                        # localised label
    veh_type  = VEHICLE_KEYS.get(veh_key, veh_key)
    context.user_data["drv_vehicle"] = veh_type

    await query.edit_message_text(t("drv_vehicle_selected", lang, label=veh_label))
    return DRV_NAME


async def drv_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    name = update.message.text.strip()
    context.user_data["drv_name"] = name
    await update.message.reply_text(
        t("drv_name_saved", lang, name=name),
        reply_markup=ReplyKeyboardRemove(),
    )
    return DRV_PLATE


async def drv_receive_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.strip().upper()
    context.user_data["drv_plate"] = plate
    lang = await get_lang(update.effective_user.id)

    # Extract plate and model from input like "CAZ 6560 WagonR"
    parts = plate.split()
    if len(parts) >= 3:
        plate_num = " ".join(parts[:2])
        model     = " ".join(parts[2:])
        plate_display = f"{plate_num} • {model}"
    else:
        plate_display = plate

    # Fetch system rate to display to driver
    from utils.fare import get_vehicle_rates
    veh_type = context.user_data.get("drv_vehicle", "car")
    _, sys_rate, _, _ = await get_vehicle_rates(veh_type)

    # Convert rate to emoji digit string e.g. 120 → 1️⃣ 2️⃣ 0️⃣
    digit_emoji = {
        "0": "0️⃣", "1": "1️⃣", "2": "2️⃣", "3": "3️⃣",
        "4": "4️⃣", "5": "5️⃣", "6": "6️⃣", "7": "7️⃣",
        "8": "8️⃣", "9": "9️⃣",
    }
    rate_str   = str(int(sys_rate))
    rate_emoji = " ".join(digit_emoji.get(c, c) for c in rate_str)

    await update.message.reply_text(
        t("drv_rate_prompt", lang, plate=plate_display, rate_emoji=rate_emoji),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(t("drv_skip_rate", lang))]], resize_keyboard=True
        ),
    )
    return DRV_RATE


async def drv_receive_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle driver's personal per-km rate input."""
    lang = await get_lang(update.effective_user.id)
    text = update.message.text.strip()
    # Match skip button in both EN and SI
    skip_texts = [
        t("drv_skip_rate", "en").lower(),
        t("drv_skip_rate", "si").lower(),
        "skip",
    ]

    if text.lower() in skip_texts:
        context.user_data["drv_rate"] = None
    else:
        try:
            rate = float(text)
            if rate <= 0:
                await update.message.reply_text(
                    t("drv_invalid_rate", lang),
                    reply_markup=ReplyKeyboardMarkup(
                        [[KeyboardButton(t("drv_skip_rate", lang))]], resize_keyboard=True
                    ),
                )
                return DRV_RATE
            context.user_data["drv_rate"] = rate
        except ValueError:
            await update.message.reply_text(
                t("drv_invalid_rate", lang),
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton(t("drv_skip_rate", lang))]], resize_keyboard=True
                ),
            )
            return DRV_RATE

    rate_display = f"LKR {context.user_data['drv_rate']}/km" if context.user_data.get("drv_rate") else "System rate"
    await update.message.reply_text(
        t("drv_rate_saved", lang, rate=rate_display),
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(t("drv_next_btn", lang))]], resize_keyboard=True
        ),
    )
    return DRV_LOCATION_INFO


async def drv_location_info_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    await update.message.reply_text(
        t("drv_share_location", lang),
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(t("drv_checkin_btn", lang), request_location=True)]],
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
    # Save optional personal rate
    rate = context.user_data.get("drv_rate")
    await db.set_driver_rate(user.id, rate)

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

    lang = await get_lang(user.id)
    name  = context.user_data.get("drv_name", "")
    plate = context.user_data.get("drv_plate", "")
    rate  = context.user_data.get("drv_rate")
    rate_label = f"LKR {rate}/km" if rate else "System rate"
    await update.message.reply_text(
        t("drv_registered", lang, name=name, plate=plate, rate=rate_label),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(t("drv_next_btn", lang))]], resize_keyboard=True
        ),
    )
    return DRV_DONE


async def drv_final_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    driver = await db.get_driver(update.effective_user.id)
    is_muted = driver["is_muted"] if driver else False
    await update.message.reply_text(
        t("drv_dashboard", lang),
        reply_markup=driver_dashboard_keyboard(is_muted),
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Dashboard actions
# ─────────────────────────────────────────────
async def drv_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    user = update.effective_user
    lang = await get_lang(user.id)
    if loc:
        await db.update_driver_location(user.id, loc.latitude, loc.longitude)
        driver = await db.get_driver(user.id)
        is_muted = driver["is_muted"] if driver else False
        await update.message.reply_text(t("drv_location_updated", lang))
        await update.message.reply_text(
            t("drv_dashboard", lang),
            reply_markup=driver_dashboard_keyboard(is_muted),
        )
    else:
        await update.message.reply_text(t("drv_update_location_prompt", lang))


async def drv_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    await db.set_driver_mute(update.effective_user.id, True)
    await update.message.reply_text(
        t("drv_muted", lang),
        reply_markup=driver_dashboard_keyboard(is_muted=True),
    )


async def drv_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    await db.set_driver_mute(update.effective_user.id, False)
    await update.message.reply_text(
        t("drv_unmuted", lang),
        reply_markup=driver_dashboard_keyboard(is_muted=False),
    )


async def drv_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_lang(user.id)
    await update.message.reply_text(
        t("back_to_menu", lang),
        reply_markup=await main_keyboard(user.id),
    )


async def drv_update_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_lang(user.id)
    driver = await db.get_driver(user.id)
    if not driver:
        await update.message.reply_text(t("drv_not_registered", lang))
        return
    await update.message.reply_text(
        t("drv_update_location_prompt", lang),
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(t("btn_send_location_drv", lang), request_location=True)]],
            resize_keyboard=True,
        ),
    )


async def drv_rate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current per-km rate and prompt driver to change it."""
    user = update.effective_user
    lang = await get_lang(user.id)
    driver = await db.get_driver(user.id)
    if not driver:
        await update.message.reply_text(t("drv_not_registered", lang))
        return

    current_rate = driver["rate_per_km"]
    if current_rate is not None:
        rate_info = t("drv_current_rate", lang, rate=current_rate)
    else:
        from utils.fare import get_vehicle_rates
        _, sys_rate, _, _ = await get_vehicle_rates(driver["vehicle_type"] or "car")
        rate_info = t("drv_using_system_rate", lang, rate=sys_rate)

    context.user_data["awaiting_rate_change"] = True
    await update.message.reply_text(
        t("drv_rate_menu", lang, rate_info=rate_info),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton(t("btn_keep_rate", lang))],
                [KeyboardButton(t("btn_system_rate", lang))],
            ],
            resize_keyboard=True,
        ),
    )


async def drv_handle_rate_change(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    if not context.user_data.get("awaiting_rate_change"):
        return False

    text = update.message.text.strip()
    user = update.effective_user
    lang = await get_lang(user.id)
    driver = await db.get_driver(user.id)
    is_muted = driver["is_muted"] if driver else False

    keep_texts = [t("btn_keep_rate", "en"), t("btn_keep_rate", "si")]
    sys_texts  = [t("btn_system_rate", "en"), t("btn_system_rate", "si")]

    if text in keep_texts:
        context.user_data.pop("awaiting_rate_change", None)
        await update.message.reply_text(
            t("drv_rate_unchanged", lang),
            reply_markup=driver_dashboard_keyboard(is_muted),
        )
        return True

    if text in sys_texts:
        context.user_data.pop("awaiting_rate_change", None)
        await update.message.reply_text(
            "✅ Rate unchanged.",
            reply_markup=driver_dashboard_keyboard(is_muted),
        )
        return True


    try:
        new_rate = float(text)
        if new_rate <= 0:
            await update.message.reply_text(t("drv_rate_positive", lang))
            return True
    except ValueError:
        await update.message.reply_text(
            t("drv_rate_invalid", lang),
            parse_mode="Markdown",
        )
        return True

    await db.set_driver_rate(user.id, new_rate)
    context.user_data.pop("awaiting_rate_change", None)
    await update.message.reply_text(
        t("drv_rate_updated", lang, rate=new_rate),
        parse_mode="Markdown",
        reply_markup=driver_dashboard_keyboard(is_muted),
    )
    return True


# ─────────────────────────────────────────────
#  ConversationHandler builder
# ─────────────────────────────────────────────
def driver_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("🚗"), driver_entry),   # 🚗 matches both EN and SI
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
            DRV_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, drv_receive_rate),
            ],
            DRV_LOCATION_INFO: [MessageHandler(filters.Regex("▶️"), drv_location_info_next)],
            DRV_LOCATION:      [MessageHandler(filters.LOCATION, drv_receive_location)],
            DRV_DONE:          [MessageHandler(filters.Regex("▶️"), drv_final_next)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )
