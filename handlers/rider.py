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
from utils.geocoding import reverse_geocode, search_location
from utils.distance import haversine
from utils.fare import calculate_fare

# ── Conversation states ───────────────────────────────────────────────────────
(
    RIDER_VEHICLE,
    RIDER_PICKUP,
    RIDER_DEST_INPUT,
    RIDER_DEST_SELECT,
    RIDER_CONFIRM,
) = range(20, 25)


def vehicle_inline_keyboard_rider() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚗 Car (3-4 Seats)",  callback_data="rveh_car")],
        [InlineKeyboardButton("🛺 Tuk (2-3 Seats)",  callback_data="rveh_tuk")],
        [InlineKeyboardButton("🏍️ Bike (1 Seat)",    callback_data="rveh_bike")],
        [InlineKeyboardButton("🚐 Van (5+ Seats)",   callback_data="rveh_van")],
    ])


RVEH_LABELS = {
    "rveh_car":  ("🚗 Car",   "car"),
    "rveh_tuk":  ("🛺 Tuk",   "tuk"),
    "rveh_bike": ("🏍️ Bike",  "bike"),
    "rveh_van":  ("🚐 Van",   "van"),
}


# ─────────────────────────────────────────────
#  Entry point — "🚕 Request Ride" button
# ─────────────────────────────────────────────
async def rider_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await db.get_user(user.id)
    if db_user and db_user["is_blocked"]:
        await update.message.reply_text("🚫 You are blocked from using this service.")
        return ConversationHandler.END

    # Check for active ride
    active = await db.get_active_ride_for_rider(user.id)
    if active:
        await update.message.reply_text(
            f"⚠️ You already have an active Ride #{active['ride_id']}.\n"
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

    # Check if category is blocked
    blocked = await db.get_blocked_categories()
    if veh_type in blocked:
        await query.edit_message_text(
            f"⚠️ Sorry, {label} is currently unavailable. Please choose another vehicle."
        )
        await query.message.reply_text(
            "🚗 What type of vehicle do you need?",
            reply_markup=vehicle_inline_keyboard_rider(),
        )
        return RIDER_VEHICLE

    await query.edit_message_text(
        f"{label} selected! ✅\n\nPlease share your location (or type address) "
        "to find drivers around you.",
    )
    await query.message.reply_text(
        "📍 Share your pickup location:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Send Location", request_location=True)]],
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
        "🏁 Where is your Drop destination?\n\n"
        "Type the address or place name below.\n"
        "Example: \"Colombo Fort\", \"Bambalapitiya\" Or tap the 📎 attachment button → "
        "Location → search and pin your destination on the map.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return RIDER_DEST_INPUT


async def rider_dest_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    results = await search_location(query_text)

    if not results:
        await update.message.reply_text(
            "❌ No results found. Please try a different address."
        )
        return RIDER_DEST_INPUT

    context.user_data["dest_results"] = results

    buttons = []
    for i, r in enumerate(results):
        buttons.append([InlineKeyboardButton(
            f"{i+1}. {r['name']}", callback_data=f"dest_{i}"
        )])

    await update.message.reply_text(
        f"📍 Found {len(results)} results for \"{query_text}\":",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return RIDER_DEST_SELECT


async def rider_dest_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle if rider shares location directly for destination."""
    loc = update.message.location
    dropoff_name = await reverse_geocode(loc.latitude, loc.longitude)
    context.user_data["dropoff_lat"] = loc.latitude
    context.user_data["dropoff_lon"] = loc.longitude
    context.user_data["dropoff_name"] = dropoff_name
    return await _show_fare_estimate(update, context, is_callback=False)


async def rider_dest_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    idx = int(query.data.split("_")[1])
    results = context.user_data.get("dest_results", [])
    if idx >= len(results):
        await query.edit_message_text("Invalid selection, please try again.")
        return RIDER_DEST_INPUT

    selected = results[idx]
    context.user_data["dropoff_lat"] = selected["lat"]
    context.user_data["dropoff_lon"] = selected["lon"]
    context.user_data["dropoff_name"] = selected["name"]

    # Send a map pin for the selected location
    try:
        await query.message.reply_location(
            latitude=selected["lat"],
            longitude=selected["lon"],
        )
    except Exception:
        pass

    await query.edit_message_text(f"✅ Drop-off set: {selected['name']}")
    return await _show_fare_estimate(update, context, is_callback=True)


async def _show_fare_estimate(update, context: ContextTypes.DEFAULT_TYPE,
                               is_callback: bool = False):
    """Show fare estimate and confirm/cancel buttons."""
    ud = context.user_data
    pickup_lat  = ud["pickup_lat"]
    pickup_lon  = ud["pickup_lon"]
    dropoff_lat = ud["dropoff_lat"]
    dropoff_lon = ud["dropoff_lon"]
    pickup_name  = ud.get("pickup_name", "Pickup")
    dropoff_name = ud.get("dropoff_name", "Drop-off")
    vehicle_label = ud.get("rider_vehicle_label", "Car")

    # Check route cache first
    cached = await db.get_cached_route(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)
    if cached:
        dist = cached["distance_km"]
        fare, base_fare, per_km, base_km, waiting_rate = await calculate_fare(dist)
    else:
        dist = haversine(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)
        dist = round(dist, 2)
        fare, base_fare, per_km, base_km, waiting_rate = await calculate_fare(dist)
        # Store in cache
        await db.set_cached_route(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon, dist, fare)

    ud["est_distance"] = dist
    ud["est_fare"] = fare
    ud["base_fare"] = base_fare
    ud["per_km"] = per_km
    ud["base_km"] = base_km

    text = (
        f"🚕 *PickRide — Fare Estimate*\n\n"
        f"📍 Pickup: {pickup_name}\n"
        f"🏁 Drop-off: {dropoff_name}\n"
        f"🚗 Vehicle: {vehicle_label}\n"
        f"✏ Distance: {dist} km\n"
        f"💰 Rate: First {base_km} km = LKR {base_fare}, then LKR {per_km}/km\n"
        f"💰 Total Fare: LKR {fare}\n\n"
        f"Confirm your ride to notify nearby drivers."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm Ride", callback_data="ride_confirm"),
            InlineKeyboardButton("❌ Cancel",       callback_data="ride_cancel"),
        ]
    ])

    # Properly get the message target
    if is_callback:
        # Called from CallbackQuery context
        query = update.callback_query
        target = query.message
    else:
        # Called from regular message context
        target = update.message

    await target.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    return RIDER_CONFIRM


async def rider_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "ride_cancel":
        await query.edit_message_text("❌ Ride request cancelled.")
        await query.message.reply_text(
            "Please choose an action from menu below 👇",
            reply_markup=await main_keyboard(update.effective_user.id),
        )
        return ConversationHandler.END

    # Confirm ride
    ud = context.user_data
    user = update.effective_user

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

    await query.edit_message_text(
        f"Ride #{ride_id} created ✅\n\n"
        f"Estimated distance: {ud['est_distance']} km\n"
        f"Estimated fare: ~LKR {ud['est_fare']}\n\n"
        f"📍 Pickup: {ud.get('pickup_name', 'Pickup')}\n"
        f"🏁 Drop-off: {ud.get('dropoff_name', 'Drop-off')}\n\n"
        f"Finding nearby drivers now..."
    )

    # Notify nearby drivers
    radius = float(await db.get_setting("driver_radius") or 8)
    nearby_drivers = await db.get_nearby_drivers(
        ud["pickup_lat"], ud["pickup_lon"], radius, ud["rider_vehicle"]
    )

    bot = context.bot
    accept_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟨 Accept", callback_data=f"accept_{ride_id}")]
    ])

    notified = 0
    for drv in nearby_drivers:
        if drv["user_id"] == user.id:
            continue
        try:
            await bot.send_message(
                drv["user_id"],
                f"🔔 *New Trip Request*\n\n"
                f"Rider *{round(drv['dist_km'], 2)} km* away\n"
                f"Estimated distance: {ud['est_distance']} km\n"
                f"Estimated fare: ~LKR {ud['est_fare']}\n"
                f"Ride #{ride_id}",
                parse_mode="Markdown",
                reply_markup=accept_keyboard,
            )
            notified += 1
        except Exception:
            pass

    if notified == 0:
        await query.message.reply_text(
            "⚠️ No drivers available nearby at the moment. Please try again later.",
            reply_markup=await main_keyboard(user.id),
        )
        await db.cancel_ride(ride_id)
    else:
        await query.message.reply_text(
            f"Sent to {notified} nearby driver(s). Waiting for acceptance...",
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
            ],
            RIDER_DEST_INPUT: [
                MessageHandler(filters.LOCATION, rider_dest_location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rider_dest_text),
            ],
            RIDER_DEST_SELECT: [
                CallbackQueryHandler(rider_dest_selected, pattern="^dest_"),
                MessageHandler(filters.LOCATION, rider_dest_location),
            ],
            RIDER_CONFIRM: [
                CallbackQueryHandler(rider_confirm, pattern="^ride_(confirm|cancel)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )
