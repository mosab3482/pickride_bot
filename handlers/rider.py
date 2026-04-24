import json
import logging

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)

import database as db
from config import GOOGLE_MAPS_API_KEY, TRIPS_GROUP_ID
from handlers.start import main_keyboard, cmd_cancel
from handlers.trip import _notify_group
from utils.geocoding import reverse_geocode, search_location
from utils.distance import haversine, get_road_distance
from utils.fare import calculate_fare, calculate_fare_for_driver, VEHICLE_EMOJIS
from utils.lang import t, get_lang

logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
(
    RIDER_VEHICLE,
    RIDER_PICKUP,
    RIDER_PICKUP_SELECT,
    RIDER_DEST_INPUT,
    RIDER_DEST_SELECT,
    RIDER_CONFIRM,          # kept for session-expired fallback
    RIDER_DRIVER_LIST,      # NEW: waiting for rider to select/contact a driver
) = range(20, 27)


def vehicle_inline_keyboard_rider(lang: str = "en") -> InlineKeyboardMarkup:
    """
    Build the vehicle-selection inline keyboard with localised button labels.
    Labels come from lang.py so Sinhala users see Sinhala names.
    """
    # seat counts stay as numbers — universally understood
    seats = {"rveh_bike": "(1)", "rveh_tuk": "(2)", "rveh_car": "(3)",
             "rveh_minivan": "(5)", "rveh_van": "(10)", "rveh_bus": "(25+)"}

    def btn(cb_key, lkey):
        return InlineKeyboardButton(
            f"{t(lkey, lang)} {seats[cb_key]}", callback_data=cb_key
        )

    return InlineKeyboardMarkup([
        [btn("rveh_bike", "veh_bike"),    btn("rveh_tuk",     "veh_tuk")],
        [btn("rveh_car",  "veh_car"),     btn("rveh_minivan", "veh_minivan")],
        [btn("rveh_van",  "veh_van"),     btn("rveh_bus",     "veh_bus")],
    ])


RVEH_LABELS = {
    "rveh_bike":    ("veh_bike",    "bike"),
    "rveh_tuk":     ("veh_tuk",     "tuk"),
    "rveh_car":     ("veh_car",     "car"),
    "rveh_minivan": ("veh_minivan", "minivan"),
    "rveh_van":     ("veh_van",     "van"),
    "rveh_bus":     ("veh_bus",     "bus"),
}


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
async def rider_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_lang(user.id)
    db_user = await db.get_user(user.id)
    if db_user and db_user["is_blocked"]:
        await update.message.reply_text(t("user_blocked", lang))
        return ConversationHandler.END

    active = await db.get_active_ride_for_rider(user.id)
    if active:
        await update.message.reply_text(t("has_active_ride", lang, ride_id=active["ride_id"]))
        return ConversationHandler.END

    await update.message.reply_text(
        t("choose_vehicle", lang),
        reply_markup=vehicle_inline_keyboard_rider(lang),
    )
    return RIDER_VEHICLE


async def rider_vehicle_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = await get_lang(query.from_user.id)

    label_key, veh_type = RVEH_LABELS[query.data]
    label = t(label_key, lang)
    context.user_data["rider_vehicle"] = veh_type
    context.user_data["rider_vehicle_label"] = label

    blocked = await db.get_blocked_categories()
    if veh_type in blocked:
        await query.edit_message_text(t("vehicle_blocked", lang, label=label))
        await query.message.reply_text(
            t("choose_vehicle", lang),
            reply_markup=vehicle_inline_keyboard_rider(lang),
        )
        return RIDER_VEHICLE

    await query.edit_message_text(t("vehicle_selected", lang, label=label))
    await query.message.reply_text(
        t("pickup_prompt", lang),
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(t("btn_send_location", lang), request_location=True)]],
            resize_keyboard=True,
        ),
    )
    return RIDER_PICKUP


async def rider_pickup_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    loc = update.message.location
    if not loc:
        await update.message.reply_text(t("pickup_prompt", lang))
        return RIDER_PICKUP

    context.user_data["pickup_lat"] = loc.latitude
    context.user_data["pickup_lon"] = loc.longitude

    pickup_name = await reverse_geocode(loc.latitude, loc.longitude, api_key=GOOGLE_MAPS_API_KEY)
    context.user_data["pickup_name"] = pickup_name

    await update.message.reply_text(
        t("pickup_confirmed", lang, name=pickup_name),
        reply_markup=ReplyKeyboardRemove(),
    )
    return RIDER_DEST_INPUT


async def rider_pickup_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let rider type a pickup location name instead of sharing GPS."""
    lang = await get_lang(update.effective_user.id)
    query_text = update.message.text.strip()
    if not query_text:
        return RIDER_PICKUP

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    results = await search_location(query_text, api_key=GOOGLE_MAPS_API_KEY)

    if not results:
        await update.message.reply_text(t("pickup_not_found", lang, query=query_text))
        return RIDER_PICKUP

    context.user_data["pickup_results"] = results
    buttons = []
    for i, r in enumerate(results):
        buttons.append([InlineKeyboardButton(
            str(i + 1) + ". " + r["name"], callback_data="pickup_" + str(i)
        )])
    buttons.append([InlineKeyboardButton(t("search_again", lang), callback_data="pickup_retry")])

    await update.message.reply_text(
        t("pickup_found", lang, n=len(results)),
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return RIDER_PICKUP_SELECT


async def rider_pickup_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rider selected pickup from search results list."""
    query = update.callback_query
    await query.answer()

async def rider_pickup_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = await get_lang(query.from_user.id)

    if query.data == "pickup_retry":
        await query.edit_message_text(t("pickup_retry_prompt", lang))
        return RIDER_PICKUP

    idx = int(query.data.split("_")[1])
    results = context.user_data.get("pickup_results", [])
    if idx >= len(results):
        await query.edit_message_text(t("invalid_selection", lang))
        return RIDER_PICKUP

    selected = results[idx]
    context.user_data["pickup_lat"]  = selected["lat"]
    context.user_data["pickup_lon"]  = selected["lon"]
    context.user_data["pickup_name"] = selected["full_name"]

    try:
        await query.message.reply_location(latitude=selected["lat"], longitude=selected["lon"])
    except Exception:
        pass

    await query.edit_message_text(t("pickup_set", lang, name=selected["name"]))
    await query.message.reply_text(
        t("dest_prompt", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    return RIDER_DEST_INPUT


async def rider_dest_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update.effective_user.id)
    query_text = update.message.text.strip()
    if not query_text:
        return RIDER_DEST_INPUT

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    results = await search_location(query_text, api_key=GOOGLE_MAPS_API_KEY)

    if not results:
        await update.message.reply_text(t("dest_not_found_tips", lang, query=query_text))
        return RIDER_DEST_INPUT

    context.user_data["dest_results"] = results
    buttons = []
    for i, r in enumerate(results):
        buttons.append([InlineKeyboardButton(
            str(i + 1) + ". " + r["name"], callback_data="dest_" + str(i)
        )])
    buttons.append([InlineKeyboardButton(t("search_again", lang), callback_data="dest_retry")])

    await update.message.reply_text(
        t("dest_found_results", lang, n=len(results), query=query_text),
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return RIDER_DEST_SELECT


async def rider_dest_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    dropoff_name = await reverse_geocode(loc.latitude, loc.longitude, api_key=GOOGLE_MAPS_API_KEY)
    context.user_data["dropoff_lat"] = loc.latitude
    context.user_data["dropoff_lon"] = loc.longitude
    context.user_data["dropoff_name"] = dropoff_name
    return await _show_driver_list(update, context, is_callback=False)


async def rider_dest_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = await get_lang(query.from_user.id)

    if query.data == "dest_retry":
        await query.edit_message_text(t("dest_retry_prompt", lang))
        return RIDER_DEST_INPUT

    try:
        idx = int(query.data.split("_")[1])
    except (IndexError, ValueError):
        await query.edit_message_text(t("invalid_selection", lang))
        return RIDER_DEST_INPUT

    results = context.user_data.get("dest_results", [])
    if idx >= len(results):
        await query.edit_message_text(t("invalid_selection", lang))
        return RIDER_DEST_INPUT

    selected = results[idx]
    context.user_data["dropoff_lat"] = selected["lat"]
    context.user_data["dropoff_lon"] = selected["lon"]
    context.user_data["dropoff_name"] = selected["name"]

    try:
        await query.message.reply_location(latitude=selected["lat"], longitude=selected["lon"])
    except Exception:
        pass

    await query.edit_message_text(t("dropoff_set", lang, name=selected["name"]))
    return await _show_driver_list(update, context, is_callback=True)


# ─────────────────────────────────────────────
#  Driver List — new central function
# ─────────────────────────────────────────────
async def _build_driver_list_messages(
    drivers: list,
    dist_km: float,
    vehicle_type: str,
    ride_id: int,
    tried_ids: set,
    lang: str = "en",
) -> list[tuple[str, InlineKeyboardMarkup]]:
    """
    Build one (text, keyboard) tuple per driver for the selection list.
    Returns list of (text, InlineKeyboardMarkup).
    """
    cards = []
    for idx, drv in enumerate(drivers, start=1):
        driver_rate = drv.get("rate_per_km")  # may be None
        fare, _, per_km, _, _ = await calculate_fare_for_driver(
            dist_km, vehicle_type=vehicle_type, driver_rate_per_km=driver_rate
        )
        rate_display = f"LKR {per_km}/km"
        fare_display = f"LKR {fare}"

        # Build availability label
        if drv["user_id"] in tried_ids:
            status_line = t("drv_card_waiting", lang)
        else:
            status_line = t("drv_card_available", lang)

        # Plate display
        plate = drv.get("plate_number") or "—"

        # Rating
        rc = drv.get("rating_count", 0)
        rs = drv.get("rating_sum", 0)
        if rc and rc > 0:
            rating_str = f"{rs/rc:.1f}⭐"
        else:
            rating_str = t("drv_card_new", lang)

        text = (
            f"{idx}️⃣ {drv['full_name']}  {rating_str}\n"
            f"🚘 {plate}\n"
            f"✏ Distance: {dist_km} km\n"
            f"💰 {rate_display}\n"
            f"💰 Est. Fare: {fare_display}\n"
            f"📍 {drv['dist_km']} km away\n"
            f"{status_line}"
        )

        # Buttons — callbacks so the bot can log each contact event
        driver_id_str = str(drv["user_id"])
        phone = drv.get("phone") or ""
        clean_phone = phone.replace("+", "").replace(" ", "")

        contact_row = []
        if clean_phone:
            contact_row.append(InlineKeyboardButton(
                "💬 WhatsApp",
                callback_data=f"contact_wa_{ride_id}_{driver_id_str}",
            ))
        # Telegram deep-link works for any user (no username needed)
        contact_row.append(InlineKeyboardButton(
            "✈️ Telegram",
            callback_data=f"contact_tg_{ride_id}_{driver_id_str}",
        ))
        if clean_phone:
            contact_row.append(InlineKeyboardButton(
                "📞 Call",
                callback_data=f"contact_call_{ride_id}_{driver_id_str}",
            ))

        select_row = []
        if drv["user_id"] not in tried_ids:
            select_row.append(InlineKeyboardButton(
                t("btn_select_driver", lang),
                callback_data=f"seldrv_{ride_id}_{drv['user_id']}",
            ))
        else:
            select_row.append(InlineKeyboardButton(
                t("btn_waiting", lang), callback_data="noop"
            ))

        kb_rows = [contact_row, select_row]
        cards.append((text, InlineKeyboardMarkup(kb_rows)))
    return cards


async def _show_driver_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    is_callback: bool = False,
    tried_ids: set | None = None,
):
    """Calculate route, fetch drivers, create ride, display driver cards."""
    user = update.effective_user
    lang = await get_lang(user.id)
    ud = context.user_data
    pickup_lat   = ud["pickup_lat"]
    pickup_lon   = ud["pickup_lon"]
    dropoff_lat  = ud["dropoff_lat"]
    dropoff_lon  = ud["dropoff_lon"]
    pickup_name  = ud.get("pickup_name", "Pickup")
    dropoff_name = ud.get("dropoff_name", "Drop-off")
    vehicle_type = ud.get("rider_vehicle", "car")
    vehicle_label = ud.get("rider_vehicle_label", "Car")
    tried_ids = tried_ids or set()

    # ── Distance calculation ───────────────────────────────────────────────────
    cached = await db.get_cached_route(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)
    if cached:
        dist = cached["distance_km"]
        dist_method = "cached"
    else:
        method = (await db.get_setting("distance_method") or "osrm").lower()
        if GOOGLE_MAPS_API_KEY and method != "haversine":
            method = "google"
        dist, dist_method = await get_road_distance(
            pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
            api_key=GOOGLE_MAPS_API_KEY,
            method=method,
        )
        # Cache with a placeholder fare (0) — actual fare varies per driver
        await db.set_cached_route(
            pickup_lat, pickup_lon, dropoff_lat, dropoff_lon, dist, 0
        )

    ud["est_distance"] = dist

    dist_labels = {
        "google":    " 🌐",
        "osrm":      " 🗺️",
        "haversine": " 📐 (est.)",
        "cached":    " 💾",
    }
    dist_note = dist_labels.get(dist_method, "")

    # ── Fetch nearby drivers ───────────────────────────────────────────────────
    radius = float(await db.get_setting("driver_radius") or 8)
    drivers = await db.get_drivers_for_ride(
        pickup_lat, pickup_lon, radius, vehicle_type
    )

    target = update.callback_query.message if is_callback else update.message

    if not drivers:
        await target.reply_text(
            t("no_drivers_available", lang, label=vehicle_label),
            reply_markup=await main_keyboard(user.id),
        )
        ud.clear()
        return ConversationHandler.END

    # ── Create ride in DB (once) ───────────────────────────────────────────────
    user = update.effective_user
    if not ud.get("ride_id"):
        # Use a placeholder fare; actual fare depends on selected driver
        placeholder_fare, *_ = await calculate_fare(dist, vehicle_type=vehicle_type)
        ride_id = await db.create_ride(
            rider_id=user.id,
            vehicle_type=vehicle_type,
            pickup_lat=pickup_lat,
            pickup_lon=pickup_lon,
            dropoff_lat=dropoff_lat,
            dropoff_lon=dropoff_lon,
            pickup_name=pickup_name,
            dropoff_name=dropoff_name,
            distance_km=dist,
            fare=placeholder_fare,
        )
        ud["ride_id"] = ride_id
    else:
        ride_id = ud["ride_id"]

    # ── Compute fare per driver, then sort cheapest first ─────────────────────
    for drv in drivers:
        f, *_ = await calculate_fare_for_driver(
            dist, vehicle_type=vehicle_type,
            driver_rate_per_km=drv.get("rate_per_km"),
        )
        drv["_est_fare"] = f  # attach for sorting

    drivers.sort(key=lambda d: d["_est_fare"])  # lowest fare → top

    fares = [d["_est_fare"] for d in drivers]
    fare_min = fares[0]
    fare_max = fares[-1]
    if fare_min == fare_max:
        fare_range_str = f"LKR {fare_min}"
    else:
        fare_range_str = f"LKR {fare_min} – {fare_max}"

    veh_emoji = VEHICLE_EMOJIS.get(vehicle_type, "🚗")

    # ── Send rider's booking summary ───────────────────────────────────────────
    rider_summary = t(
        "ride_summary", lang,
        veh=veh_emoji, label=vehicle_label,
        pickup=pickup_name, dropoff=dropoff_name,
        dist=dist, note=dist_note,
        fare_range=fare_range_str, n=len(drivers),
    )
    await target.reply_text(rider_summary, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

    # Store serialised driver list so it can be restored after bot restart
    candidates_json = json.dumps([
        {
            "user_id":      drv["user_id"],
            "full_name":    drv["full_name"],
            "plate_number": drv.get("plate_number"),
            "dist_km":      drv["dist_km"],
            "phone":        drv.get("phone"),
            "rate_per_km":  drv.get("rate_per_km"),
            "rating_sum":   drv.get("rating_sum", 0),
            "rating_count": drv.get("rating_count", 0),
        }
        for drv in drivers
    ])
    await db.save_driver_candidates(ride_id, candidates_json)
    ud["driver_candidates"] = drivers
    ud["tried_driver_ids"]   = list(tried_ids)

    # ── Send one card per driver ───────────────────────────────────────────────
    cards = await _build_driver_list_messages(
        drivers, dist, vehicle_type, ride_id, tried_ids, lang
    )
    for card_text, kb in cards:
        await target.reply_text(card_text, reply_markup=kb)

    return RIDER_DRIVER_LIST


# ─────────────────────────────────────────────
#  Rider contacts a driver (Call / WhatsApp)
# ─────────────────────────────────────────────
async def rider_contact_driver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles contact_call_{ride_id}_{driver_id} and
              contact_wa_{ride_id}_{driver_id} button taps.
    Logs the contact to the trips group, then sends the rider the link.
    """
    query = update.callback_query
    await query.answer()

    parts  = query.data.split("_")   # ["contact", "call"|"wa", ride_id, driver_id]
    method = parts[1]                 # "call" or "wa"
    ride_id   = int(parts[2])
    driver_id = int(parts[3])
    rider     = update.effective_user
    ud        = context.user_data

    # ── Look up driver details from candidate list (or DB fallback) ───────────
    candidates = ud.get("driver_candidates") or []
    if not candidates:
        cand_json = await db.get_driver_candidates(ride_id)
        if cand_json:
            candidates = json.loads(cand_json)

    drv = next((d for d in candidates if d["user_id"] == driver_id), None)
    if not drv:
        drv_row  = await db.get_driver(driver_id)
        drv_user = await db.get_user(driver_id)
        drv = {
            "full_name":    drv_row["full_name"]    if drv_row  else "Driver",
            "plate_number": drv_row["plate_number"] if drv_row  else "",
            "phone":        drv_user["phone"]        if drv_user else "",
        }

    driver_name  = drv.get("full_name", "Driver")
    phone        = drv.get("phone") or ""
    clean_phone  = phone.replace("+", "").replace(" ", "")

    # ── Rider info ────────────────────────────────────────────────────────────
    rider_user  = await db.get_user(rider.id)
    rider_name  = rider_user["first_name"] if rider_user else rider.first_name
    rider_tag   = f"@{rider_user['username']}" if rider_user and rider_user.get("username") else rider_name
    rider_phone = rider_user["phone"] if rider_user and rider_user.get("phone") else "N/A"

    pickup_name  = ud.get("pickup_name", "")
    dropoff_name = ud.get("dropoff_name", "")
    vehicle_label = ud.get("rider_vehicle_label", ud.get("rider_vehicle", "vehicle"))
    lang = await get_lang(rider.id)

    if method == "call":
        channel      = "📞 Phone Call"
        rider_action = f"📞 *Driver's number (tap to call):*\n`{phone}`"
        rider_link_kb = None
    elif method == "wa":
        channel      = "💬 WhatsApp"
        rider_action = t("contact_wa_action", lang)
        rider_link_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(t("btn_open_whatsapp", lang), url=f"https://wa.me/{clean_phone}")
        ]]) if clean_phone else None
    else:  # tg
        channel      = "✈️ Telegram"
        rider_action = t("contact_tg_action", lang)
        tg_url = f"tg://user?id={driver_id}"
        rider_link_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(t("btn_open_telegram", lang), url=tg_url)
        ]])

    # ── Notify trips group ────────────────────────────────────────────────────
    group_msg = (
        f"📲 *Rider Contacted Driver — Ride #{ride_id}*\n\n"
        f"📡 Channel: {channel}\n\n"
        f"👤 *Rider:* {rider_tag}\n"
        f"📞 Rider Phone: {rider_phone}\n\n"
        f"🚗 *Driver:* {driver_name}\n"
        f"🚘 Plate: {drv.get('plate_number') or '—'}\n"
        f"📞 Driver Phone: {phone or 'N/A'}\n\n"
        f"🚙 Vehicle: {vehicle_label}\n"
        f"📍 Pickup:   {pickup_name}\n"
        f"🏁 Drop-off: {dropoff_name}"
    )
    await _notify_group(context.bot, TRIPS_GROUP_ID, group_msg)

    # ── Reply to rider ────────────────────────────────────────────────────────
    if method == "call":
        # Inline markdown link inside message text — tappable on mobile, opens dialer
        await query.message.reply_text(
            f"[📞 Call {driver_name}](tel:{phone})",
            parse_mode="Markdown",
        )
    else:
        await query.message.reply_text(
            f"{rider_action}",
            parse_mode="Markdown",
            reply_markup=rider_link_kb,
        )


# ─────────────────────────────────────────────
#  Rider selects a driver
# ─────────────────────────────────────────────
async def rider_select_driver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles seldrv_{ride_id}_{driver_user_id} button taps."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    # callback_data = "seldrv_{ride_id}_{driver_user_id}"
    ride_id   = int(parts[1])
    driver_id = int(parts[2])
    user      = update.effective_user
    ud        = context.user_data

    # ── Restore ride data if context was lost (bot restart) ───────────────────
    if not ud.get("ride_id"):
        ud["ride_id"] = ride_id
        cand_json = await db.get_driver_candidates(ride_id)
        if cand_json:
            ud["driver_candidates"] = json.loads(cand_json)
        ud["tried_driver_ids"] = []

    # Track which drivers the rider has already tried
    tried = set(ud.get("tried_driver_ids", []))
    if driver_id in tried:
        await query.answer("⏳ Already waiting for that driver.", show_alert=True)
        return RIDER_DRIVER_LIST

    tried.add(driver_id)
    ud["tried_driver_ids"] = list(tried)

    # ── Assign this driver to the ride ────────────────────────────────────────
    await db.assign_driver_to_ride(ride_id, driver_id)

    # ── Find driver details from candidate list ────────────────────────────────
    candidates = ud.get("driver_candidates") or []
    selected_drv = next((d for d in candidates if d["user_id"] == driver_id), None)

    if not selected_drv:
        # Fallback: load from DB
        drv_row   = await db.get_driver(driver_id)
        drv_user  = await db.get_user(driver_id)
        selected_drv = {
            "full_name":   drv_row["full_name"] if drv_row else "Driver",
            "plate_number": drv_row["plate_number"] if drv_row else "",
            "phone":        drv_user["phone"] if drv_user else "",
            "rate_per_km":  drv_row["rate_per_km"] if drv_row else None,
            "dist_km":      0,
        }

    driver_name = selected_drv["full_name"]
    vehicle_type = ud.get("rider_vehicle", "car")
    dist_km      = ud.get("est_distance", 0)

    # Recalculate fare with this driver's personal rate for the DB update
    drv_rate = selected_drv.get("rate_per_km")
    fare, _, per_km, _, _ = await calculate_fare_for_driver(
        dist_km, vehicle_type=vehicle_type, driver_rate_per_km=drv_rate
    )

    # Update fare on the ride
    await db.set_cached_route(
        ud.get("pickup_lat", 0), ud.get("pickup_lon", 0),
        ud.get("dropoff_lat", 0), ud.get("dropoff_lon", 0),
        dist_km, fare,
    )

    # ── Notify the driver with Accept button ───────────────────────────────────
    pickup_name  = ud.get("pickup_name", "Pickup")
    dropoff_name = ud.get("dropoff_name", "Drop-off")

    rider_user = await db.get_user(user.id)
    rider_phone = rider_user["phone"] if rider_user and rider_user["phone"] else "N/A"
    rider_name  = rider_user["first_name"] if rider_user else user.first_name
    rider_tag   = f"@{rider_user['username']}" if rider_user and rider_user.get("username") else rider_name

    accept_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟨 Accept Ride", callback_data=f"accept_{ride_id}")]
    ])

    try:
        await context.bot.send_message(
            driver_id,
            f"🔔 *Rider Request — Ride #{ride_id}*\n\n"
            f"👤 Rider: {rider_tag}\n"
            f"📞 Contact: {rider_phone}\n\n"
            f"📍 Pickup:   {pickup_name}\n"
            f"🏁 Drop-off: {dropoff_name}\n"
            f"✏ Distance: {dist_km} km\n"
            f"💰 Your Rate: LKR {per_km}/km\n"
            f"💰 Est. Fare: LKR {fare}\n\n"
            f"Rider has selected YOU. Tap Accept to confirm:",
            parse_mode="Markdown",
            reply_markup=accept_kb,
        )
    except Exception as e:
        logger.warning(f"Could not notify driver {driver_id}: {e}")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"⚠️ Could not reach {driver_name}. Please select another driver."
        )
        return RIDER_DRIVER_LIST

    # ── Update button in the card the rider tapped ────────────────────────────
    try:
        phone = selected_drv.get("phone") or ""
        clean_phone = phone.replace("+", "").replace(" ", "")
        btn_row = []
        if clean_phone:
            btn_row.append(InlineKeyboardButton("📞 Call", url=f"tel:%2B{clean_phone}"))
            btn_row.append(InlineKeyboardButton("💬 WhatsApp", url=f"https://wa.me/{clean_phone}"))
        btn_row.append(InlineKeyboardButton("⏳ Request Sent…", callback_data="noop"))
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([btn_row])
        )
    except Exception:
        pass

    lang = await get_lang(user.id)
    # ── Tell rider what happened ───────────────────────────────────────────────
    await query.message.reply_text(
        t("request_sent", lang, name=driver_name, fare=fare),
        parse_mode="Markdown",
    )

    # Notify TRIPS group
    trip_group_msg = (
        f"🔔 *Rider Selected Driver — Ride #{ride_id}*\n\n"
        f"👤 Rider: {rider_tag}\n"
        f"🚗 Vehicle: {ud.get('rider_vehicle_label', vehicle_type).title()}\n"
        f"📍 Pickup:   {pickup_name}\n"
        f"🏁 Drop-off: {dropoff_name}\n"
        f"✏ Distance: {dist_km} km\n"
        f"🚗 Driver: {driver_name}\n"
        f"💰 Est. Fare: LKR {fare}"
    )
    await _notify_group(context.bot, TRIPS_GROUP_ID, trip_group_msg)

    return RIDER_DRIVER_LIST


# ─────────────────────────────────────────────
#  rider_confirm — kept as global fallback
#  (handles ride_confirm / ride_cancel from
#   sessions that pre-date this new flow)
# ─────────────────────────────────────────────
async def rider_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang  = await get_lang(query.from_user.id)
    try:
        await query.answer()
    except Exception as e:
        logger.error(f"rider_confirm: query.answer() failed: {e}")
        return ConversationHandler.END

    if query.data == "ride_cancel":
        await query.edit_message_text(t("ride_cancelled_rider", lang))
        await query.message.reply_text(
            t("back_to_menu", lang),
            reply_markup=await main_keyboard(update.effective_user.id),
        )
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text(
        t("choose_vehicle", lang)
    )
    await query.message.reply_text(
        t("back_to_menu", lang),
        reply_markup=await main_keyboard(update.effective_user.id),
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  ConversationHandler builder
# ─────────────────────────────────────────────
def rider_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex("🚕"),   # matches both EN (🚕 Request Ride) and SI (🚕 ටැක්සියක් ගන්න) buttons
            rider_entry
        )],
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
            RIDER_DRIVER_LIST: [
                CallbackQueryHandler(rider_contact_driver, pattern=r"^contact_(call|wa|tg)_\d+_\d+$"),
                CallbackQueryHandler(rider_select_driver,  pattern=r"^seldrv_\d+_\d+$"),
            ],
            RIDER_CONFIRM: [
                CallbackQueryHandler(rider_confirm, pattern="^ride_(confirm|cancel)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
        per_message=False,
    )
