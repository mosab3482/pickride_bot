from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)

import database as db
from config import GOOGLE_MAPS_API_KEY
from handlers.start import main_keyboard, cmd_cancel
from utils.geocoding import reverse_geocode, search_location
from utils.distance import haversine, get_road_distance
from utils.fare import calculate_fare

# ── Conversation states ───────────────────────────────────────────────────────
(
    RIDER_VEHICLE,
    RIDER_PICKUP,
    RIDER_PICKUP_SELECT,
    RIDER_DEST_INPUT,
    RIDER_DEST_SELECT,
    RIDER_CONFIRM,
) = range(20, 26)


def vehicle_inline_keyboard_rider() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛺 Tuk (2 Seats)",      callback_data="rveh_tuk"),
         InlineKeyboardButton("🚗 Car (3 Seats)",      callback_data="rveh_car")],
        [InlineKeyboardButton("🚙 Mini Van (5 Seats)", callback_data="rveh_minivan"),
         InlineKeyboardButton("🚐 Van (10 Seats)",     callback_data="rveh_van")],
        [InlineKeyboardButton("🚌 Bus (25+ Seats)",    callback_data="rveh_bus")],
    ])


RVEH_LABELS = {
    "rveh_tuk":     ("🛺 Tuk",     "tuk"),
    "rveh_car":     ("🚗 Car",     "car"),
    "rveh_minivan": ("🚙 Mini Van", "minivan"),
    "rveh_van":     ("🚐 Van",     "van"),
    "rveh_bus":     ("🚌 Bus",     "bus"),
}


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
async def rider_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await db.get_user(user.id)
    if db_user and db_user["is_blocked"]:
        await update.message.reply_text("🚫 You are blocked from using this service.")
        return ConversationHandler.END

    active = await db.get_active_ride_for_rider(user.id)
    if active:
        await update.message.reply_text(
            "⚠️ You already have an active Ride #" + str(active["ride_id"]) + ".\n"
            "Use /cancelride to cancel it first."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🚗 What type of vehicle do you need?",
        reply_markup=vehicle_inline_keyboard_rider(),
    )
    return RIDER_VEHICLE


async def rider_vehicle_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    label, veh_type = RVEH_LABELS[query.data]
    context.user_data["rider_vehicle"] = veh_type
    context.user_data["rider_vehicle_label"] = label

    blocked = await db.get_blocked_categories()
    if veh_type in blocked:
        await query.edit_message_text(
            "⚠️ Sorry, " + label + " is currently unavailable. Please choose another vehicle."
        )
        await query.message.reply_text(
            "🚗 What type of vehicle do you need?",
            reply_markup=vehicle_inline_keyboard_rider(),
        )
        return RIDER_VEHICLE

    await query.edit_message_text(label + " selected! ✅")
    await query.message.reply_text(
        "📍 Where is your pickup location?\n\n"
        "• 📌 Tap the button to share your GPS location\n"
        "• ✏️ Or type the pickup place name (e.g. Colombo Fort)",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Send My Location", request_location=True)]],
            resize_keyboard=True,
        ),
    )
    return RIDER_PICKUP


async def rider_pickup_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    if not loc:
        await update.message.reply_text("Please use the button to share your location.")
        return RIDER_PICKUP

    context.user_data["pickup_lat"] = loc.latitude
    context.user_data["pickup_lon"] = loc.longitude

    pickup_name = await reverse_geocode(loc.latitude, loc.longitude)
    context.user_data["pickup_name"] = pickup_name

    await update.message.reply_text(
        f"✅ Pickup set: {pickup_name}\n\n"
        "🏁 Where do you want to go?\n\n"
        "Type the place name in English (e.g. Kandy, Galle Fort)\n"
        "Or tap 📎 → Location to pin on map.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return RIDER_DEST_INPUT


async def rider_pickup_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let rider type a pickup location name instead of sharing GPS."""
    query_text = update.message.text.strip()
    if not query_text:
        return RIDER_PICKUP

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    results = await search_location(query_text)

    if not results:
        await update.message.reply_text(
            "❌ No pickup locations found for: " + query_text + "\n\n"
            "Try a different name, or use the 📍 Send My Location button."
        )
        return RIDER_PICKUP

    context.user_data["pickup_results"] = results
    buttons = []
    for i, r in enumerate(results):
        buttons.append([InlineKeyboardButton(
            str(i + 1) + ". " + r["name"], callback_data="pickup_" + str(i)
        )])
    buttons.append([InlineKeyboardButton("🔍 Search Again", callback_data="pickup_retry")])

    await update.message.reply_text(
        "📍 Found " + str(len(results)) + " pickup locations:\nChoose yours:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return RIDER_PICKUP_SELECT


async def rider_pickup_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rider selected pickup from search results list."""
    query = update.callback_query
    await query.answer()

    if query.data == "pickup_retry":
        await query.edit_message_text(
            "🔍 Type the pickup place name:",
        )
        return RIDER_PICKUP

    idx = int(query.data.split("_")[1])
    results = context.user_data.get("pickup_results", [])
    if idx >= len(results):
        await query.edit_message_text("⚠️ Invalid selection. Please try again.")
        return RIDER_PICKUP

    selected = results[idx]
    context.user_data["pickup_lat"]  = selected["lat"]
    context.user_data["pickup_lon"]  = selected["lon"]
    context.user_data["pickup_name"] = selected["full_name"]

    try:
        await query.message.reply_location(latitude=selected["lat"], longitude=selected["lon"])
    except Exception:
        pass

    await query.edit_message_text("✅ Pickup set: " + selected["name"])
    await query.message.reply_text(
        "🏁 Where do you want to go?\n\n"
        "Type the destination name in English (e.g. Kandy, Galle Fort)\n"
        "Or tap 📎 → Location to pin on map.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return RIDER_DEST_INPUT


async def rider_dest_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    if not query_text:
        return RIDER_DEST_INPUT

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    results = await search_location(query_text)

    if not results:
        await update.message.reply_text(
            "❌ No results found for: " + query_text + "\n\n"
            "Tips:\n"
            "• Type the name in English\n"
            "• Try a shorter name (e.g. Colombo instead of Colombo Fort Station)\n"
            "• Share your location directly using 📎 attachment button"
        )
        return RIDER_DEST_INPUT

    context.user_data["dest_results"] = results

    buttons = []
    for i, r in enumerate(results):
        buttons.append([InlineKeyboardButton(
            str(i + 1) + ". " + r["name"], callback_data="dest_" + str(i)
        )])
    buttons.append([InlineKeyboardButton("🔍 Search Again", callback_data="dest_retry")])

    await update.message.reply_text(
        "📍 Found " + str(len(results)) + " results for \"" + query_text + "\":\n"
        "Choose your destination:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return RIDER_DEST_SELECT


async def rider_dest_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    dropoff_name = await reverse_geocode(loc.latitude, loc.longitude)
    context.user_data["dropoff_lat"] = loc.latitude
    context.user_data["dropoff_lon"] = loc.longitude
    context.user_data["dropoff_name"] = dropoff_name
    return await _show_fare_estimate(update, context, is_callback=False)


async def rider_dest_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "dest_retry":
        await query.edit_message_text(
            "🔍 Type the destination name:\n"
            "(Example: Colombo, Kandy, Galle)"
        )
        return RIDER_DEST_INPUT

    try:
        idx = int(query.data.split("_")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("⚠️ Invalid selection. Please type the name again.")
        return RIDER_DEST_INPUT

    results = context.user_data.get("dest_results", [])
    if idx >= len(results):
        await query.edit_message_text("⚠️ Result not found. Please type the name again.")
        return RIDER_DEST_INPUT

    selected = results[idx]
    context.user_data["dropoff_lat"] = selected["lat"]
    context.user_data["dropoff_lon"] = selected["lon"]
    context.user_data["dropoff_name"] = selected["name"]

    try:
        await query.message.reply_location(
            latitude=selected["lat"],
            longitude=selected["lon"],
        )
    except Exception:
        pass

    await query.edit_message_text("✅ Drop-off set: " + selected["name"])
    return await _show_fare_estimate(update, context, is_callback=True)


async def _show_fare_estimate(update, context: ContextTypes.DEFAULT_TYPE,
                               is_callback: bool = False):
    ud = context.user_data
    pickup_lat   = ud["pickup_lat"]
    pickup_lon   = ud["pickup_lon"]
    dropoff_lat  = ud["dropoff_lat"]
    dropoff_lon  = ud["dropoff_lon"]
    pickup_name  = ud.get("pickup_name", "Pickup")
    dropoff_name = ud.get("dropoff_name", "Drop-off")
    vehicle_label = ud.get("rider_vehicle_label", "Car")

    # Try Google Maps first, fallback to Haversine×1.3
    cached = await db.get_cached_route(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)
    if cached:
        dist = cached["distance_km"]
        fare, base_fare, per_km, base_km, waiting_rate = await calculate_fare(dist)
        dist_method = "cached"
    else:
        dist, dist_method = await get_road_distance(
            pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
            api_key=GOOGLE_MAPS_API_KEY,
        )
        fare, base_fare, per_km, base_km, waiting_rate = await calculate_fare(dist)
        await db.set_cached_route(
            pickup_lat, pickup_lon, dropoff_lat, dropoff_lon, dist, fare
        )

    ud["est_distance"] = dist
    ud["est_fare"]     = fare

    # Show distance source indicator
    dist_note = ""
    if dist_method == "google":
        dist_note = " (road)"
    elif dist_method == "haversine":
        dist_note = " (est.)"

    text = (
        "🚕 PickRide — Fare Estimate\n\n"
        "📍 Pickup:   " + pickup_name + "\n"
        "🏁 Drop-off: " + dropoff_name + "\n"
        "🚗 Vehicle:  " + vehicle_label + "\n\n"
        "✏ Distance: " + str(dist) + " km" + dist_note + "\n"
        "💵 Rate: First " + str(base_km) + " km = LKR " + str(base_fare) +
        ", then LKR " + str(per_km) + "/km\n"
        "💰 Total Fare: LKR " + str(fare) + "\n\n"
        "Confirm your ride to notify nearby drivers."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm Ride", callback_data="ride_confirm"),
            InlineKeyboardButton("❌ Cancel",       callback_data="ride_cancel"),
        ]
    ])

    if is_callback:
        target = update.callback_query.message
    else:
        target = update.message

    await target.reply_text(text, reply_markup=keyboard)
    return RIDER_CONFIRM


async def rider_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger = __import__("logging").getLogger(__name__)

    try:
        await query.answer()
    except Exception as e:
        logger.error(f"rider_confirm: query.answer() failed: {e}")
        return ConversationHandler.END

    try:
        if query.data == "ride_cancel":
            await query.edit_message_text("❌ Ride request cancelled.")
            await query.message.reply_text(
                "Back to main menu:",
                reply_markup=await main_keyboard(update.effective_user.id),
            )
            context.user_data.clear()
            return ConversationHandler.END

        # Guard: ensure ride data is still in context
        ud = context.user_data
        required = ["rider_vehicle", "pickup_lat", "pickup_lon",
                    "dropoff_lat", "dropoff_lon", "est_distance", "est_fare"]
        if not all(k in ud for k in required):
            await query.edit_message_text(
                "⚠️ Session expired. Please start a new ride request.\n\n"
                "Tap 🚕 Request Ride from the main menu."
            )
            await query.message.reply_text(
                "Back to main menu:",
                reply_markup=await main_keyboard(update.effective_user.id),
            )
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"rider_confirm setup error: {e}", exc_info=True)
        try:
            await query.message.reply_text("Error processing request. Please try again.")
        except Exception:
            pass
        return ConversationHandler.END

    user = update.effective_user

    try:
        ride_id = await db.create_ride(
            rider_id=user.id,
            vehicle_type=ud["rider_vehicle"],
            pickup_lat=ud["pickup_lat"],
            pickup_lon=ud["pickup_lon"],
            dropoff_lat=ud["dropoff_lat"],
            dropoff_lon=ud["dropoff_lon"],
            pickup_name=ud.get("pickup_name", "Unknown"),
            dropoff_name=ud.get("dropoff_name", "Unknown"),
            distance_km=ud["est_distance"],
            fare=ud["est_fare"],
        )
    except Exception as e:
        logger.error(f"rider_confirm: create_ride failed: {e}", exc_info=True)
        await query.message.reply_text(
            "Failed to create ride (database error). Please try again or use /start."
        )
        return ConversationHandler.END

    await query.edit_message_text(
        "✅ Ride #" + str(ride_id) + " created!\n\n"
        "📍 Pickup:   " + ud.get("pickup_name", "Pickup") + "\n"
        "🏁 Drop-off: " + ud.get("dropoff_name", "Drop-off") + "\n"
        "✏ Distance: " + str(ud["est_distance"]) + " km\n"
        "💰 Fare:     ~LKR " + str(ud["est_fare"]) + "\n\n"
        "🔍 Finding nearby drivers..."
    )

    radius = float(await db.get_setting("driver_radius") or 8)
    nearby_drivers = await db.get_nearby_drivers(
        ud["pickup_lat"], ud["pickup_lon"], radius, ud["rider_vehicle"]
    )

    bot = context.bot
    accept_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟨 Accept Ride", callback_data="accept_" + str(ride_id))]
    ])

    notified = 0
    pickup_name  = ud.get("pickup_name", "N/A")
    dropoff_name = ud.get("dropoff_name", "N/A")

    for drv in nearby_drivers:
        if drv["user_id"] == user.id:
            continue
        try:
            await bot.send_message(
                drv["user_id"],
                "🔔 New Ride Request!\n\n"
                "📍 Pickup:   " + pickup_name + "\n"
                "🏁 Drop-off: " + dropoff_name + "\n"
                "✏ Distance: " + str(ud["est_distance"]) + " km\n"
                "💰 Est. Fare: LKR " + str(ud["est_fare"]) + "\n\n"
                "🧭 Rider is " + str(round(drv["dist_km"], 2)) + " km from you\n\n"
                "Tap Accept to take this ride:",
                reply_markup=accept_keyboard,
            )
            notified += 1
        except Exception:
            pass

    if notified == 0:
        await query.message.reply_text(
            "⚠️ No drivers available nearby at the moment.\n"
            "Please try again later.",
            reply_markup=await main_keyboard(user.id),
        )
        await db.cancel_ride(ride_id)
    else:
        await query.message.reply_text(
            "📡 Request sent to " + str(notified) + " driver(s).\n"
            "Waiting for acceptance...",
            reply_markup=await main_keyboard(user.id),
        )

    context.user_data.clear()
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  ConversationHandler builder
# ─────────────────────────────────────────────
def rider_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚕 Request Ride$"), rider_entry)],
        states={
            RIDER_VEHICLE: [
                CallbackQueryHandler(rider_vehicle_selected, pattern="^rveh_"),
            ],
            RIDER_PICKUP: [
                MessageHandler(filters.LOCATION, rider_pickup_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rider_pickup_text_search),
            ],
            RIDER_PICKUP_SELECT: [
                CallbackQueryHandler(rider_pickup_selected, pattern="^pickup_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rider_pickup_text_search),
                MessageHandler(filters.LOCATION, rider_pickup_received),
            ],
            RIDER_DEST_INPUT: [
                MessageHandler(filters.LOCATION, rider_dest_location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rider_dest_text),
            ],
            RIDER_DEST_SELECT: [
                CallbackQueryHandler(rider_dest_selected, pattern="^dest_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rider_dest_text),
                MessageHandler(filters.LOCATION, rider_dest_location),
            ],
            RIDER_CONFIRM: [
                CallbackQueryHandler(rider_confirm, pattern="^ride_(confirm|cancel)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
        per_message=False,
    )
