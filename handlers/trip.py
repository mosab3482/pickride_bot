from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

import database as db
from config import TRIPS_GROUP_ID
from handlers.start import main_keyboard
from handlers.driver import driver_dashboard_keyboard
from utils.distance import haversine, cumulative_distance
from utils.fare import calculate_fare
from utils.geocoding import reverse_geocode


# ── Helper: send to groups silently, never raise ──────────────────────────────
async def _notify_group(bot, chat_id, text: str, parse_mode="Markdown"):
    """Send a message to a group/channel, silently ignoring any errors."""
    if not chat_id:
        return
    try:
        await bot.send_message(chat_id, text, parse_mode=parse_mode)
    except Exception:
        pass


# ─────────────────────────────────────────────
#  Accept Ride (driver presses Accept button)
# ─────────────────────────────────────────────
async def accept_ride_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    driver_id = update.effective_user.id
    ride_id = int(query.data.split("_")[1])

    # Atomically try to accept
    success = await db.accept_ride(ride_id, driver_id)
    if not success:
        await query.edit_message_text(
            "✔️ You replied to this ☝️ order. Expect a call from the passenger to confirm.\n\n"
            "⚠️ This ride was already accepted by another driver."
        )
        return

    await query.edit_message_text(
        "✔️ You replied to this ☝️ order. Expect a call from the passenger to confirm."
    )

    ride = await db.get_ride(ride_id)
    rider = await db.get_user(ride["rider_id"])
    driver = await db.get_driver(driver_id)
    driver_user = await db.get_user(driver_id)

    # Format location names
    pickup_name  = ride["pickup_name"] or f"{ride['pickup_lat']:.4f},{ride['pickup_lon']:.4f}"
    dropoff_name = ride["dropoff_name"] or f"{ride['dropoff_lat']:.4f},{ride['dropoff_lon']:.4f}"

    # Google Maps DIRECTION links (free, no API usage)
    # Driver current location → Pickup
    drv_lat = driver["current_lat"] if driver and driver["current_lat"] else ride["pickup_lat"]
    drv_lon = driver["current_lon"] if driver and driver["current_lon"] else ride["pickup_lon"]
    pickup_nav_link = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={drv_lat},{drv_lon}"
        f"&destination={ride['pickup_lat']},{ride['pickup_lon']}"
    )
    # Pickup → Drop-off
    dropoff_nav_link = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={ride['pickup_lat']},{ride['pickup_lon']}"
        f"&destination={ride['dropoff_lat']},{ride['dropoff_lon']}"
    )

    rider_username = (
        f"@{rider['username']}" if rider and rider["username"]
        else rider["first_name"] if rider else "Rider"
    )
    rider_phone = rider["phone"] if rider and rider["phone"] else "N/A"
    driver_name  = driver["full_name"] if driver else "Driver"

    dist_km = ride["distance_km"]
    fare    = ride["fare"]

    # ── Driver notification: full trip details + navigation + WhatsApp ──────────
    rider_wa_btn = []
    if rider_phone and rider_phone != "N/A":
        clean_rider_phone = rider_phone.replace("+", "").replace(" ", "")
        rider_wa_btn = [
            InlineKeyboardButton(
                "📞 Call/WhatsApp Rider",
                url=f"https://wa.me/{clean_rider_phone}",
            )
        ]

    # Build pickup pinpoint link for Google Maps (opens map at exact pin)

    nav_kb_rows = [
        [
            InlineKeyboardButton(
                "🗺 Navigate to PICKUP",
                url=(
                    f"https://www.google.com/maps/dir/?api=1"
                    f"&origin={drv_lat},{drv_lon}"
                    f"&destination={ride['pickup_lat']},{ride['pickup_lon']}"
                    f"&travelmode=driving"
                ),
            )
        ],
    ]
    if rider_wa_btn:
        nav_kb_rows.append(rider_wa_btn)
    nav_kb_rows += [
        [InlineKeyboardButton("⚠️ SET METER TO 0️⃣ — 🟢 START TRIP 🟢", callback_data=f"starttrip_{ride_id}")],
    ]
    nav_kb = InlineKeyboardMarkup(nav_kb_rows)

    await query.message.reply_text(
        f"🎉 You've accepted Ride \#{ride_id}!\n\n"
        f"👤 Rider: {rider_username}\n"
        f"📞 Contact: {rider_phone}\n"
        f"✏ Distance: {dist_km} km\n"
        f"💰 Fare: LKR {fare}\n\n"
        f"📍 Pickup:   {pickup_name}\n"
        f"🏁 Drop-off: {dropoff_name}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 *SET YOUR VEHICLE METER TO 0️⃣*\n"
        f"*BEFORE PRESSING START TRIP\!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 *Tap START TRIP when rider is in the vehicle:*",
        parse_mode="Markdown",
        reply_markup=nav_kb,
    )

    # ── Notify rider: driver is coming + driver WhatsApp button ──────────────
    driver_phone  = driver_user["phone"] if driver_user else "N/A"
    rider_alert_btns = []
    if driver_phone and driver_phone != "N/A":
        clean_drv_phone = driver_phone.replace("+", "").replace(" ", "")
        rider_alert_btns.append(
            [InlineKeyboardButton("📞 Call/WhatsApp Driver", url=f"https://wa.me/{clean_drv_phone}")]
        )

    # Fetch driver rating
    driver_rating = await db.get_driver_rating(driver_id)

    # Fetch waiting rate for this vehicle type (for transparency in rider notification)
    from utils.fare import get_vehicle_rates as _get_rates
    _, _, _base_km, _waiting_rate = await _get_rates(ride["vehicle_type"] or "car")

    await context.bot.send_message(
        ride["rider_id"],
        f"✅ Ride #{ride_id} accepted!\n\n"
        f"🚗 Driver: {driver_name} {driver_rating}\n"
        f"📞 Contact: {driver_phone}\n\n"
        f"📍 Pickup:   {pickup_name}\n"
        f"🏁 Drop-off: {dropoff_name}\n"
        f"✏ Distance: {dist_km} km\n"
        f"💰 Est. Fare: LKR {fare}\n"
        f"⏱ Waiting Rate: LKR {_waiting_rate}/min *(system rate)*\n\n"
        f"Driver is on the way. Please wait at the pickup location.",
        reply_markup=InlineKeyboardMarkup(rider_alert_btns) if rider_alert_btns else None,
    )


# ─────────────────────────────────────────────
#  Start Trip — Immediate (no location required)
# ─────────────────────────────────────────────
async def start_trip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    driver_id = update.effective_user.id
    ride_id   = int(query.data.split("_")[1])
    ride      = await db.get_ride(ride_id)

    if not ride or ride["status"] != "accepted":
        await query.edit_message_text("⚠️ Cannot start this trip.")
        return

    # Use driver's last known check-in location (from DB)
    driver = await db.get_driver(driver_id)
    lat = driver["current_lat"] if driver and driver["current_lat"] else None
    lon = driver["current_lon"] if driver and driver["current_lon"] else None

    # Start the ride in DB
    await db.start_ride(ride_id)

    # Record starting location point if available
    if lat and lon:
        await db.add_location_point(ride_id, driver_id, lat, lon)

    context.user_data["active_trip"] = ride_id

    pickup_lat   = ride["pickup_lat"]
    pickup_lon   = ride["pickup_lon"]
    dropoff_lat  = ride["dropoff_lat"]
    dropoff_lon  = ride["dropoff_lon"]
    pickup_name  = ride["pickup_name"]  or "Pickup"
    dropoff_name = ride["dropoff_name"] or "Drop-off"

    # Driver current location (for navigate-to-pickup link)
    drv_lat = lat or pickup_lat
    drv_lon = lon or pickup_lon

    # After trip starts → show only DROP-OFF navigation
    nav_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🏁 Navigate to DROP-OFF",
            url=(
                f"https://www.google.com/maps/dir/?api=1"
                f"&origin={pickup_lat},{pickup_lon}"
                f"&destination={dropoff_lat},{dropoff_lon}"
                f"&travelmode=driving"
            ),
        )],
    ])

    end_trip_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("🔴 End Trip")]],
        resize_keyboard=True,
    )
    await query.message.reply_text(
        f"🟢 Trip #{ride_id} has started!\n\n"
        f"📍 Pickup:   {pickup_name}\n"
        f"🏁 Drop-off: {dropoff_name}\n\n"
        f"Use the navigation buttons below 👇",
        reply_markup=nav_kb,
    )
    await query.message.reply_text(
        "Tap End Trip when you complete the ride.",
        reply_markup=end_trip_kb,
    )

    # Notify rider
    await context.bot.send_message(
        ride["rider_id"],
        f"🟢 Your trip #{ride_id} has started!\n\n"
        f"The driver is on the way to your drop-off location."
    )


async def share_location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Legacy handler — kept for compatibility but redirects to start_trip_callback."""
    query = update.callback_query
    await query.answer()
    ride_id = int(query.data.split("_")[1])
    # Simulate start trip
    context.user_data["starting_ride"] = ride_id
    await query.edit_message_text("📍 Please tap 🟢 Start Trip to begin the ride.")


async def handle_start_trip_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kept for backwards compatibility — no longer used in normal flow."""
    ride_id = context.user_data.get("starting_ride")
    if not ride_id:
        return

    loc = update.message.location
    if not loc:
        return

    ride = await db.get_ride(ride_id)
    if not ride or ride["status"] != "accepted":
        return

    await db.start_ride(ride_id)
    await db.add_location_point(ride_id, update.effective_user.id, loc.latitude, loc.longitude)
    context.user_data.pop("starting_ride", None)
    context.user_data["active_trip"] = ride_id

    end_trip_kb = ReplyKeyboardMarkup([[KeyboardButton("🔴 End Trip")]], resize_keyboard=True)
    await update.message.reply_text(
        f"🟢 Trip #{ride_id} started!\n\nTap END TRIP when you complete the ride.",
        reply_markup=end_trip_kb,
    )
    await context.bot.send_message(ride["rider_id"], f"🟢 Trip #{ride_id} has started!")


# ─────────────────────────────────────────────
#  End Trip — Step 1: Ask for meter distance
# ─────────────────────────────────────────────
async def handle_end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    active_ride = await db.get_active_ride_for_driver(user.id)

    if not active_ride or active_ride["status"] != "in_progress":
        await update.message.reply_text("⚠️ No active trip found.")
        return

    ride_id = active_ride["ride_id"]

    # Calculate GPS distance from stored location points (survives restart)
    points_rows = await db.get_location_points(ride_id)
    points = [(r["lat"], r["lon"]) for r in points_rows]

    if len(points) >= 2:
        gps_dist = round(cumulative_distance(points), 2)
    else:
        gps_dist = active_ride["distance_km"]

    context.user_data["ending_ride"] = ride_id
    context.user_data["gps_distance"] = gps_dist

    await update.message.reply_text(
        f"🛑 Ending Trip #{ride_id}\n\n"
        f"📍 GPS tracked distance: {gps_dist} km\n\n"
        f"📏 Enter total kilometers from your *vehicle meter*:\n"
        f"(Example: 5.2)\n\n"
        f"Or type `gps` to use GPS distance.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


async def handle_meter_distance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle driver's meter distance input."""
    ride_id = context.user_data.get("ending_ride")
    if not ride_id:
        return False  # Not in end-trip flow

    text = update.message.text.strip().lower()

    if text == "gps":
        distance = context.user_data.get("gps_distance", 0)
    else:
        try:
            distance = float(text)
            if distance <= 0:
                await update.message.reply_text("⚠️ Please enter a positive number.")
                return True
        except ValueError:
            await update.message.reply_text(
                "⚠️ Please enter a valid number (e.g., 5.2) or type `gps`.",
                parse_mode="Markdown",
            )
            return True

    context.user_data["final_distance"] = distance
    context.user_data["awaiting_waiting"] = True
    context.user_data.pop("ending_ride", None)  # Move to next step

    await update.message.reply_text(
        f"✅ Distance set: {distance} km\n\n"
        f"⏱ Enter *waiting time* in minutes (or `0` for none):\n"
        f"(Example: 3)",
        parse_mode="Markdown",
    )
    return True


async def handle_waiting_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle driver's waiting time input and complete the trip."""
    if not context.user_data.get("awaiting_waiting"):
        return False

    text = update.message.text.strip()
    try:
        waiting_min = float(text)
        if waiting_min < 0:
            await update.message.reply_text("⚠️ Please enter 0 or a positive number.")
            return True
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number (e.g., 3).")
        return True

    ride_id = context.user_data.get("active_trip")
    if not ride_id:
        await update.message.reply_text("⚠️ No active trip found.")
        context.user_data.clear()
        return True

    distance = context.user_data.get("final_distance", 0)
    ride     = await db.get_ride(ride_id)
    vehicle_type = ride["vehicle_type"] if ride else "car"
    fare, base_fare, per_km, base_km, waiting_rate = await calculate_fare(
        distance, waiting_min, vehicle_type=vehicle_type
    )

    await db.complete_ride(ride_id, distance, fare, waiting_min)

    # Reset driver status to online
    user = update.effective_user
    await db.set_driver_online(user.id, True)

    # Clean up user_data
    context.user_data.pop("active_trip", None)
    context.user_data.pop("final_distance", None)
    context.user_data.pop("awaiting_waiting", None)
    context.user_data.pop("gps_distance", None)

    ride = await db.get_ride(ride_id)
    rider = await db.get_user(ride["rider_id"])
    driver_user = await db.get_user(ride["driver_id"])

    rider_tag = (
        f"@{rider['username']}" if rider and rider["username"]
        else rider["first_name"] if rider else "Rider"
    )
    driver_tag = (
        f"@{driver_user['username']}" if driver_user and driver_user["username"]
        else driver_user["first_name"] if driver_user else "Driver"
    )

    # Get driver rating
    driver_rating = await db.get_driver_rating(ride["driver_id"])

    # Build waiting line — always show the configured rate; show charge only if > 0
    waiting_rate_line = f"⏱ Waiting Rate: LKR {waiting_rate}/min *(system rate)*\n"
    waiting_charge_line = ""
    if waiting_min > 0:
        waiting_charge = round(waiting_min * waiting_rate, 2)
        waiting_charge_line = f"⏱ Waiting: {waiting_min} min × LKR {waiting_rate}/min = LKR {waiting_charge}\n"

    completion_msg = (
        f"✅ TeleCabs — Trip #{ride_id} Completed!\n\n"
        f"👤 Rider: {rider_tag}\n"
        f"🚘 Driver: {driver_tag} {driver_rating}\n"
        f"📏 Distance: {distance} km\n"
        f"💵 Rate: First {base_km} km = LKR {base_fare}, then LKR {per_km}/km\n"
        f"{waiting_rate_line}"
        f"{waiting_charge_line}"
        f"💰 Total Fare: LKR {fare}\n\n"
        f"Thank you for using TeleCabs!"
    )

    # Send completion to driver
    await update.message.reply_text(completion_msg, reply_markup=await main_keyboard(user.id))

    # Post invoice to TRIPS group
    invoice_msg = (
        f"🧾 *Trip #{ride_id} Invoice*\n\n"
        f"👤 Rider: {rider_tag}\n"
        f"🚘 Driver: {driver_tag} {driver_rating}\n"
        f"📏 Distance: {distance} km\n"
        f"💵 Rate: First {base_km} km = LKR {base_fare}, then LKR {per_km}/km\n"
        f"{waiting_rate_line}"
        f"{waiting_charge_line}"
        f"💰 *Total Fare: LKR {fare}*\n"
        f"📍 Pickup:   {ride['pickup_name'] or 'N/A'}\n"
        f"🏁 Drop-off: {ride['dropoff_name'] or 'N/A'}"
    )
    await _notify_group(context.bot, TRIPS_GROUP_ID, invoice_msg)

    # Send completion + rating request to rider
    rating_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐1", callback_data=f"rate_{ride_id}_1"),
            InlineKeyboardButton("⭐2", callback_data=f"rate_{ride_id}_2"),
            InlineKeyboardButton("⭐3", callback_data=f"rate_{ride_id}_3"),
            InlineKeyboardButton("⭐4", callback_data=f"rate_{ride_id}_4"),
            InlineKeyboardButton("⭐5", callback_data=f"rate_{ride_id}_5"),
        ]
    ])
    await context.bot.send_message(ride["rider_id"], completion_msg)
    await context.bot.send_message(
        ride["rider_id"],
        "Please rate your driver:",
        reply_markup=rating_kb,
    )
    return True


# ─────────────────────────────────────────────
#  Rating callback — stars selection
# ─────────────────────────────────────────────
async def rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    ride_id = int(parts[1])
    stars   = int(parts[2])

    ride = await db.get_ride(ride_id)
    if not ride:
        await query.edit_message_text("⚠️ Ride not found.")
        return

    await db.save_rating(ride_id, update.effective_user.id, ride["driver_id"], stars)

    # After rating → ask for a comment
    await query.edit_message_text(
        f"Thank you for your {stars} ⭐️ rating!\n\n"
        f"💬 Would you like to leave a comment about your experience?\n"
        f"(Tell us anything — good or bad)\n\n"
        f"Type your comment below, or tap Skip:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Skip", callback_data=f"ratecomment_{ride_id}_skip")]
        ]),
    )
    # Store context for text handler
    context.user_data["awaiting_comment"] = {"ride_id": ride_id, "stars": stars}


async def rating_comment_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rider skipped leaving a comment."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("awaiting_comment", None)
    await query.edit_message_text("✅ Rating submitted. Thank you!")
    await query.message.reply_text(
        "Welcome back! 🚕\n\nFast and simple taxi service.",
        reply_markup=await main_keyboard(update.effective_user.id),
    )


async def handle_rating_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle rider's text comment after rating. Returns True if handled."""
    comment_data = context.user_data.get("awaiting_comment")
    if not comment_data:
        return False

    ride_id = comment_data["ride_id"]
    stars   = comment_data["stars"]
    comment = update.message.text.strip()

    # Save the comment
    await db.save_rating_comment(ride_id, update.effective_user.id, comment)
    context.user_data.pop("awaiting_comment", None)

    # Notify TRIPS group about the feedback
    rider = await db.get_user(update.effective_user.id)
    rider_tag = (
        f"@{rider['username']}" if rider and rider["username"]
        else rider["first_name"] if rider else "Rider"
    )
    rating_group_msg = (
        f"💬 *Rider Feedback — Trip #{ride_id}*\n\n"
        f"👤 Rider: {rider_tag}\n"
        f"⭐ Rating: {'⭐' * stars} ({stars}/5)\n"
        f"📝 Comment: {comment}"
    )
    await _notify_group(context.bot, TRIPS_GROUP_ID, rating_group_msg)

    await update.message.reply_text(
        f"✅ Thank you for your feedback!\n\n📝 Your comment has been recorded.",
        reply_markup=await main_keyboard(update.effective_user.id),
    )
    return True


# ─────────────────────────────────────────────
#  Live location update handler (during trip)
# ─────────────────────────────────────────────
async def live_location_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle continuous live location updates from driver during trip."""
    loc = update.message.location
    if not loc:
        return

    user_id = update.effective_user.id
    active_ride = await db.get_active_ride_for_driver(user_id)

    if not active_ride or active_ride["status"] != "in_progress":
        # Maybe it's a check-in from driver dashboard
        from handlers.driver import drv_checkin
        await drv_checkin(update, context)
        return

    ride_id = active_ride["ride_id"]
    # Store in database (persistent, survives restart)
    await db.add_location_point(ride_id, user_id, loc.latitude, loc.longitude)
    await db.update_driver_location(user_id, loc.latitude, loc.longitude)
