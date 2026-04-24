from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

import logging
import database as db
from config import TRIPS_GROUP_ID, DRIVERS_GROUP_ID, RIDERS_GROUP_ID
from handlers.start import main_keyboard
from handlers.driver import driver_dashboard_keyboard
from utils.distance import haversine, cumulative_distance
from utils.fare import calculate_fare
from utils.geocoding import reverse_geocode
from utils.lang import t, get_lang

logger = logging.getLogger(__name__)


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

    # Atomically try to accept — but now ANY driver may press Accept,
    # even if status is 'pending' with a pre-assigned driver_id.
    # We only allow the specifically assigned driver to accept.
    ride = await db.get_ride(ride_id)
    if not ride:
        await query.edit_message_text("⚠️ Ride not found.")
        return

    if ride["status"] == "accepted":
        await query.edit_message_text(
            "✔️ This ride was already accepted by another driver."
        )
        return

    # If a specific driver was pre-assigned, only they can accept
    if ride["driver_id"] and ride["driver_id"] != driver_id:
        await query.edit_message_text(
            "⚠️ A different driver was selected for this ride."
        )
        return

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
        [InlineKeyboardButton("🚨 I'VE ARRIVED AT PICKUP 🚨", callback_data=f"arrived_{ride_id}")],
    ]
    if rider_wa_btn:
        nav_kb_rows.append(rider_wa_btn)
    nav_kb_rows += [
        [InlineKeyboardButton("⚠️ SET METER TO 0️⃣ — 🟢 START TRIP 🟢", callback_data=f"starttrip_{ride_id}")],
    ]
    nav_kb = InlineKeyboardMarkup(nav_kb_rows)

    await query.message.reply_text(
        f"🎉 You've accepted Ride #{ride_id}!\n\n"
        f"👤 Rider: {rider_username}\n"
        f"📞 Contact: {rider_phone}\n"
        f"✏ Distance: {dist_km} km\n"
        f"💰 Fare: LKR {fare}\n\n"
        f"📍 Pickup:   {pickup_name}\n"
        f"🏁 Drop-off: {dropoff_name}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 *SET YOUR VEHICLE METER TO 0️⃣*\n"
        f"*BEFORE PRESSING START TRIP!*\n"
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

    # Re-calculate fare using driver's personal rate
    from utils.fare import calculate_fare_for_driver as _calc_drv_fare, get_vehicle_rates as _get_rates
    drv_row = await db.get_driver(driver_id)
    drv_rate = drv_row["rate_per_km"] if drv_row and drv_row["rate_per_km"] is not None else None
    _, _, _base_km, _waiting_rate = await _get_rates(ride["vehicle_type"] or "car")

    # Update the ride fare to reflect this driver's personal rate
    actual_fare, _, act_per_km, _, _ = await _calc_drv_fare(
        dist_km, vehicle_type=ride["vehicle_type"] or "car", driver_rate_per_km=drv_rate
    )

    rider_lang = await get_lang(ride["rider_id"])
    await context.bot.send_message(
        ride["rider_id"],
        t("driver_accepted", rider_lang,
          ride_id=ride_id,
          name=driver_name,
          rating=driver_rating,
          phone=driver_phone,
          pickup=pickup_name,
          dropoff=dropoff_name,
          dist=dist_km,
          per_km=act_per_km,
          fare=actual_fare,
          wait=_waiting_rate,
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rider_alert_btns) if rider_alert_btns else None,
    )


# ────────────────
# ─────────────────────────────
#  Arrived at Pickup — notify rider
# ─────────────────────────────
async def arrived_ride_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Rider notified! ✅", show_alert=False)

    driver_id = update.effective_user.id
    ride_id   = int(query.data.split("_")[1])
    ride      = await db.get_ride(ride_id)

    if not ride or ride["status"] not in ("pending", "accepted"):
        await query.answer("⚠️ Cannot send arrived — ride not active.", show_alert=True)
        return

    driver      = await db.get_driver(driver_id)
    driver_user = await db.get_user(driver_id)
    driver_name = driver["full_name"] if driver else "Your driver"
    driver_phone = driver_user["phone"] if driver_user and driver_user["phone"] else "N/A"

    # ── Send arrived alert to rider ───────────────────────────────────────────
    # Phone number in message text is auto-tappable on mobile (opens dialer)
    # WhatsApp button is the only URL button (tel: scheme is unreliable)
    rider_alert_btns = []
    if driver_phone and driver_phone != "N/A":
        clean = driver_phone.replace("+", "").replace(" ", "")
        rider_alert_btns.append(
            [InlineKeyboardButton("💬 WhatsApp Driver", url=f"https://wa.me/{clean}")]
        )

    try:
        rider_lang = await get_lang(ride["rider_id"])
        await context.bot.send_message(
            ride["rider_id"],
            t("driver_arrived", rider_lang, name=driver_name, phone=driver_phone),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(rider_alert_btns) if rider_alert_btns else None,
        )
    except Exception as e:
        logger.warning(f"arrived_ride_callback: could not notify rider {ride['rider_id']}: {e}")

    # ── Notify trips group ────────────────────────────────────────────────────
    rider_user = await db.get_user(ride["rider_id"])
    rider_tag  = (
        f"@{rider_user['username']}" if rider_user and rider_user.get("username")
        else rider_user["first_name"] if rider_user else "Rider"
    )
    await _notify_group(
        context.bot, TRIPS_GROUP_ID,
        f"📍 *Driver Arrived at Pickup — Ride #{ride_id}*\n\n"
        f"🚗 Driver: {driver_name}\n"
        f"📞 Driver Phone: {driver_phone}\n\n"
        f"👤 Rider: {rider_tag}\n"
        f"📍 Pickup: {ride['pickup_name'] or 'N/A'}"
    )

    # ── Update driver's button to Show START TRIP ─────────────────────────────
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Rider Notified — Arrived!", callback_data="noop")],
                [InlineKeyboardButton("⚠️ SET METER TO 0️⃣ — 🟢 START TRIP 🟢", callback_data=f"starttrip_{ride_id}")],
            ])
        )
    except Exception as e:
        logger.warning(f"arrived_ride_callback: could not edit driver message: {e}")


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
    rider_lang = await get_lang(ride["rider_id"])
    await context.bot.send_message(
        ride["rider_id"],
        t("trip_started_rider", rider_lang, ride_id=ride_id),
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

    lang = await get_lang(user.id)
    await update.message.reply_text(
        t("end_trip_prompt", lang, ride_id=ride_id, gps=gps_dist),
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
                lang = await get_lang(update.effective_user.id)
                await update.message.reply_text(t("end_trip_positive", lang))
                return True
        except ValueError:
            lang = await get_lang(update.effective_user.id)
            await update.message.reply_text(
                t("end_trip_invalid_dist", lang), parse_mode="Markdown"
            )
            return True

    context.user_data["final_distance"] = distance
    context.user_data["awaiting_waiting"] = True
    context.user_data.pop("ending_ride", None)

    lang = await get_lang(update.effective_user.id)
    await update.message.reply_text(
        t("end_trip_dist_set", lang, dist=distance),
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
            lang = await get_lang(update.effective_user.id)
            await update.message.reply_text(t("end_trip_invalid_wait", lang))
            return True
    except ValueError:
        lang = await get_lang(update.effective_user.id)
        await update.message.reply_text(t("end_trip_invalid_wait", lang))
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

    ride        = await db.get_ride(ride_id)
    rider       = await db.get_user(ride["rider_id"])
    driver_user = await db.get_user(ride["driver_id"])
    driver_rec  = await db.get_driver(ride["driver_id"])

    rider_tag   = (
        f"@{rider['username']}" if rider and rider["username"]
        else rider["first_name"] if rider else "Rider"
    )
    driver_tag  = (
        f"@{driver_user['username']}" if driver_user and driver_user["username"]
        else driver_user["first_name"] if driver_user else "Driver"
    )
    rider_phone  = rider["phone"]       if rider       and rider.get("phone")       else "N/A"
    driver_phone = driver_user["phone"] if driver_user and driver_user.get("phone") else "N/A"
    driver_name  = driver_rec["full_name"]    if driver_rec else driver_tag
    plate        = driver_rec["plate_number"] if driver_rec and driver_rec.get("plate_number") else "—"
    vtype        = ride["vehicle_type"] or "car"

    # Vehicle emoji
    from config import VEHICLE_EMOJIS
    veh_emoji = VEHICLE_EMOJIS.get(vtype, "🚗")

    # Get driver rating
    driver_rating = await db.get_driver_rating(ride["driver_id"])

    # Build waiting lines
    waiting_rate_line   = f"⏱ Waiting Rate: LKR {waiting_rate}/min\n"
    waiting_charge_line = ""
    if waiting_min > 0:
        waiting_charge      = round(waiting_min * waiting_rate, 2)
        waiting_charge_line = f"⏱ Waiting: {waiting_min} min × LKR {waiting_rate}/min = LKR {waiting_charge}\n"

    completion_msg = (
        f"✅ TeleCabs — Trip #{ride_id} Completed!\n\n"
        f"👤 Rider: {rider_tag}\n"
        f"{veh_emoji} Driver: {driver_name} {driver_rating}\n"
        f"🚘 Plate: {plate}\n"
        f"📏 Distance: {distance} km\n"
        f"💵 Rate: First {base_km} km = LKR {base_fare}, then LKR {per_km}/km\n"
        f"{waiting_rate_line}"
        f"{waiting_charge_line}"
        f"💰 Total Fare: LKR {fare}\n\n"
        f"Thank you for using TeleCabs!"
    )

    # Send completion to driver (admin message stays in English)
    await update.message.reply_text(completion_msg, reply_markup=await main_keyboard(user.id))

    # ── Build full invoice for groups (English for admin)
    invoice_msg = (
        f"🧾 *Trip Completed — Ride #{ride_id}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *Rider*\n"
        f"   Name:  {rider_tag}\n"
        f"   Phone: {rider_phone}\n\n"
        f"{veh_emoji} *Driver*\n"
        f"   Name:  {driver_name} {driver_rating}\n"
        f"   Plate: {plate}\n"
        f"   Phone: {driver_phone}\n\n"
        f"🗺 *Route*\n"
        f"   📍 Pickup:   {ride['pickup_name'] or 'N/A'}\n"
        f"   🏁 Drop-off: {ride['dropoff_name'] or 'N/A'}\n\n"
        f"💵 *Fare Breakdown*\n"
        f"   Distance:  {distance} km\n"
        f"   Base fare: LKR {base_fare} (first {base_km} km)\n"
        f"   Rate:      LKR {per_km}/km\n"
        f"   {waiting_charge_line.strip() or 'No waiting charge'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Total Fare: LKR {fare}*"
    )
    await _notify_group(context.bot, TRIPS_GROUP_ID,   invoice_msg)
    await _notify_group(context.bot, DRIVERS_GROUP_ID, invoice_msg)

    # Send completion + rating request to rider in their language
    rider_lang = await get_lang(ride["rider_id"])
    rider_completion = t(
        "trip_completed_rider", rider_lang,
        ride_id=ride_id, rider=rider_tag,
        veh=veh_emoji, driver=driver_name, rating=driver_rating,
        plate=plate, dist=distance,
        base_km=base_km, base_fare=base_fare, per_km=per_km,
        waiting=waiting_charge_line, fare=fare,
    )
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
    rider_lang = await get_lang(update.effective_user.id)
    # After rating → ask for a comment
    await query.edit_message_text(
        t("rate_thanks", rider_lang, stars=stars),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_skip", rider_lang), callback_data=f"ratecomment_{ride_id}_skip")]
        ]),
    )
    context.user_data["awaiting_comment"] = {"ride_id": ride_id, "stars": stars}


async def rating_comment_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rider skipped leaving a comment."""
    query = update.callback_query
    await query.answer()
    rider_lang = await get_lang(query.from_user.id)
    context.user_data.pop("awaiting_comment", None)
    await query.edit_message_text(t("rate_submitted", rider_lang))
    await query.message.reply_text(
        t("back_to_menu", rider_lang),
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
    rider_lang = await get_lang(update.effective_user.id)

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
        t("rate_feedback_thanks", rider_lang),
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
