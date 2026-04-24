"""
Language / translation helper for TeleCabs bot.
Supported languages: 'en' (English), 'si' (Sinhala / සිංහල)
"""

import database as db

SUPPORTED = ("en", "si")
DEFAULT   = "en"

# ── Translation table ──────────────────────────────────────────────────────────
_T: dict[str, dict[str, str]] = {

    # ── Language selection ─────────────────────────────────────────────────────
    "lang_choose": {
        "en": "🌐 Please choose your language:",
        "si": "🌐 කරුණාකර ඔබේ භාෂාව තෝරන්න:",
    },
    "lang_set": {
        "en": "✅ Language set to *English*.",
        "si": "✅ භාෂාව *සිංහල* ලෙස සකසා ඇත.",
    },

    # ── Welcome / start ────────────────────────────────────────────────────────
    "welcome": {
        "en": "👋 *Welcome to TeleCabs 🚕*\n\nFast and simple taxi service.",
        "si": "👋 *TeleCabs 🚕 සේවාවට සාදරයෙන් පිළිගනිමු!*\n\nඉක්මන් සහ පහසු ටැක්සි සේවාව.",
    },

    # ── Main keyboard buttons ──────────────────────────────────────────────────
    "btn_request_ride": {
        "en": "🚕 Request Ride",
        "si": "🚕 ටැක්සියක් ගන්න",
    },
    "btn_im_driver": {
        "en": "🚗 I'm a Driver",
        "si": "🚗 මම රියදුරෙක්",
    },
    "btn_update_location": {
        "en": "📍 Update My Location",
        "si": "📍 ස්ථානය යාවත්කාලීන කරන්න",
    },
    "btn_cancel_ride": {
        "en": "🟥 Cancel Current Ride",
        "si": "🟥 වත්මන් ගමන අවලංගු කරන්න",
    },
    "btn_help": {
        "en": "ℹ️ Help",
        "si": "ℹ️ උදව්",
    },
    "btn_admin": {
        "en": "👑 Admin Control ⚙️",
        "si": "👑 Admin Control ⚙️",
    },
    "btn_language": {
        "en": "🌐 Language",
        "si": "🌐 භාෂාව",
    },

    # ── Help ───────────────────────────────────────────────────────────────────
    "help_text": {
        "en": (
            "TeleCabs — Help\n\n"
            "🚕 *Request Ride* — Book a taxi\n"
            "🚗 *I'm a Driver* — Register or go online as driver\n"
            "📍 *Update My Location* — Update your GPS position\n"
            "🟥 *Cancel Current Ride* — Cancel active booking\n\n"
            "*Commands:*\n"
            "/start — Return to main menu\n"
            "/cancel — Cancel current action\n"
            "/cancelride — Cancel active ride"
        ),
        "si": (
            "TeleCabs — Help\n\n"
            "🚕 *ටැක්සියක් ගන්න* — ටැක්සියක් වෙන්කරගන්න\n"
            "🚗 *මම රියදුරෙක්* — රියදුරෙක් ලෙස ලියාපදිංචි වන්න / Online වන්න\n"
            "📍 *ස්ථානය යාවත්කාලීන කරන්න* — ඔබගේ GPS ස්ථානය යවන්න\n"
            "🟥 *වත්මන් ගමන අවලංගු කරන්න* — දැනට ඇති booking එක cancel කරන්න\n\n"
            "Commands: /start — ප්රධාන මෙනුවට යන්න\n"
            "/cancel — වත්මන් ක්රියාව නවත්වන්න\n"
            "/cancelride — active ride එක cancel කරන්න"
        ),
    },

    # ── Cancel ─────────────────────────────────────────────────────────────────
    "action_cancelled": {
        "en": "❌ Action cancelled.",
        "si": "❌ ක්‍රියාව අවලංගු කරන ලදී.",
    },

    # ── Ride request flow ──────────────────────────────────────────────────────
    "choose_vehicle": {
        "en": "🚗 What type of vehicle do you need?",
        "si": "🚗 ඔබට කුමන වාහන වර්ගයක් අවශ්‍යද?",
    },
    "vehicle_blocked": {
        "en": "⚠️ Sorry, {label} is currently unavailable. Please choose another vehicle.",
        "si": "⚠️ සමාවෙන්න, {label} දැනට ලබා ගත නොහැක. කරුණාකර වෙනත් වාහනයක් තෝරන්න.",
    },

    # ── Vehicle type labels ─────────────────────────────────────────────────────
    "veh_tuk": {"en": "🛺 Tuk",     "si": "🛺 ත්රිවිල්"},
    "veh_bike": {"en": "🏍️ Bike",   "si": "🏍️ යතුරුපැදි"},
    "veh_car": {"en": "🚗 Car",     "si": "🚗 කාර්"},
    "veh_minivan": {"en": "🚙 Mini Van", "si": "🚙 මිනි වෑන්"},
    "veh_van": {"en": "🚐 Van",     "si": "🚐 වෑන්"},
    "veh_bus": {"en": "🚌 Bus",     "si": "🚌 බස්"},
    "vehicle_selected": {
        "en": "{label} selected! ✅",
        "si": "{label} තෝරා ගන්නා ලදී! ✅",
    },
    "pickup_prompt": {
        "en": "📍 Share your pickup location\n\n• Tap to send GPS 📌\n• Or type location (e.g. Colombo Fort)",
        "si": "📍 ඔබගේ සිටිනා ස්ථානය යවන්න\n\n• GPS යවන්න ටැප් කරන්න 📌\n• නැත්නම් ස්ථානය ටයිප් කරන්න (උදා: Colombo Fort)",
    },
    "dest_prompt": {
        "en": "🏁 Enter your drop location\n• Type place (e.g. Kandy)\n• Or send location 📎",
        "si": "🏁 ගමනාන්ත ස්ථානය ඇතුළත් කරන්න\n• ස්ථාන නාමය ටයිප් කරන්න (උදා: මහනුවර)\n• හෝ ස්ථානය යවන්න 📎",
    },
    "pickup_confirmed": {
        "en": "✅ Pickup: {name}\n\n🏁 Enter your drop location\n• Type place (e.g. Kandy)\n• Or send location 📎",
        "si": "✅ ලබාගැනීමේ ස්ථානය: {name}\n\n🏁 ගමනාන්ත ස්ථානය ඇතුළත් කරන්න\n• ස්ථාන නාමය ටයිප් කරන්න (උදා: මහනුවර)\n• හෝ ස්ථානය යවන්න 📎",
    },
    "no_drivers": {
        "en": "⚠️ No drivers available nearby for {label} right now.\nPlease try again later.",
        "si": "⚠️ දැනට {label} සඳහා ළඟ රියදුරන් නොමැත.\nකරුණාකර පසුව නැවත උත්සාහ කරන්න.",
    },
    "ride_request_summary": {
        "en": "🎟️ *Your Ride Request*",
        "si": "🎟️ *ඔබගේ ගමන් ඉල්ලීම*",
    },
    "available_drivers": {
        "en": "🚗 *Available Drivers ({n}):*\n⚠️ Please contact a driver before selecting",
        "si": "🚗 *පවතින රියදුරන් ({n}):*\n⚠️ කරුණාකර රියදුරෙකු තෝරා ගැනීමට පෙර සම්බන්ධ වන්න",
    },
    "btn_select": {
        "en": "✅ Select",
        "si": "✅ තෝරන්න",
    },
    "request_sent": {
        "en": "📡 Request sent to *{name}*!\n\n💰 Est. Fare with this driver: LKR {fare}\n\n⏳ Waiting for acceptance…\n\nIf the driver doesn't respond, you can select another driver above. No need to start over!",
        "si": "📡 *{name}* වෙත ඉල්ලීම යවන ලදී!\n\n💰 මෙම රියදුරු සමඟ ගෙවීම: LKR {fare}\n\n⏳ පිළිගැනීම් බලාපොරොත්තු වෙමින්...\n\nරියදුරා ප්‍රතිචාර නොදක්වයි නම්, ඉහතින් වෙනත් රියදුරෙකු තෝරන්න. නැවත ආරම්භ කිරීම අවශ්‍ය නොවේ!",
    },
    "driver_accepted": {
        "en": "✅ Ride #{ride_id} accepted!\n\n🚗 Driver: {name} {rating}\n📞 Contact: {phone}\n\n📍 Pickup:   {pickup}\n🏁 Drop-off: {dropoff}\n✏ Distance: {dist} km\n💰 Rate: LKR {per_km}/km\n💰 Est. Fare: LKR {fare}\n⏱ Waiting Rate: LKR {wait}/min\n\n✅ Driver confirmed! He is on the way.\nPlease wait at the pickup location.",
        "si": "✅ ගමන #{ride_id} පිළිගන්නා ලදී!\n\n🚗 රියදුරු: {name} {rating}\n📞 සම්බන්ධතා: {phone}\n\n📍 ලබාගැනීම:   {pickup}\n🏁 ගමනාන්ත:   {dropoff}\n✏ දුර: {dist} km\n💰 මිල: LKR {per_km}/km\n💰 ගෙවිය යුතු: LKR {fare}\n⏱ රැඳී සිටීමේ මිල: LKR {wait}/min\n\n✅ රියදුරු තහවුරු කරන ලදී! ඔහු එමින් සිටී.\nකරුණාකර ලබාගැනීමේ ස්ථානයේ රැඳී සිටින්න.",
    },
    "driver_arrived": {
        "en": "🚨 *Your driver has arrived!*\n\n🚗 Driver: {name}\n📞 Tap to call: {phone}\n\nPlease head to the pickup location now.",
        "si": "🚨 *ඔබගේ රියදුරු පැමිණ ඇත!*\n\n🚗 රියදුරු: {name}\n📞 ඇමතීමට누르න්න: {phone}\n\nකරුණාකර දැන් ලබාගැනීමේ ස්ථානයට යන්න.",
    },
    "trip_started": {
        "en": "🟢 Your trip #{ride_id} has started!\n\nThe driver is on the way to your drop-off location.",
        "si": "🟢 ඔබගේ ගමන #{ride_id} ආරම්භ වී ඇත!\n\nරියදුරා ඔබගේ ගමනාන්ත ස්ථානය වෙත ළඟා වෙමින් සිටී.",
    },
    "trip_completed": {
        "en": "✅ TeleCabs — Trip #{ride_id} Completed!\n\n👤 Rider: {rider}\n🚘 Driver: {driver} {rating}\n🚘 Plate: {plate}\n📏 Distance: {dist} km\n💵 Rate: First {base_km} km = LKR {base_fare}, then LKR {per_km}/km\n{waiting}\n💰 Total Fare: LKR {fare}\n\nThank you for using TeleCabs!",
        "si": "✅ TeleCabs — ගමන #{ride_id} සම්පූර්ණ විය!\n\n👤 මගී: {rider}\n🚘 රියදුරු: {driver} {rating}\n🚘 Plate: {plate}\n📏 දුර: {dist} km\n💵 මිල: පළමු {base_km} km = LKR {base_fare}, ඉන්පසු LKR {per_km}/km\n{waiting}\n💰 මුළු ගෙවීම: LKR {fare}\n\nTeleCabs භාවිතා කිරීමට ස්තූතියි!",
    },
    "rate_driver": {
        "en": "Please rate your driver:",
        "si": "කරුණාකර ඔබගේ රියදුරු ශ්‍රේණිගත කරන්න:",
    },
    "ride_cancelled_rider": {
        "en": "❌ Ride request cancelled.",
        "si": "❌ ගමන් ඉල්ලීම අවලංගු කරන ලදී.",
    },
    "btn_send_location": {
        "en": "📍 Send My Location",
        "si": "📍 මගේ ස්ථානය යවන්න",
    },

    # ── Rider blocked / active ride ────────────────────────────────────────────
    "user_blocked": {
        "en": "🚫 You are blocked from using this service.",
        "si": "🚫 ඔබව මෙම සේවාවෙන් අවහිර කර ඇත.",
    },
    "has_active_ride": {
        "en": "⚠️ You already have an active Ride #{ride_id}.\nUse /cancelride to cancel it first.",
        "si": "⚠️ ඔබට දැනටමත් සක්‍රිය ගමනක් ඇත #{ride_id}.\nඑය ඉවත් කිරීමට /cancelride භාවිතා කරන්න.",
    },
    "pickup_not_found": {
        "en": "❌ No pickup locations found for: {query}\n\nTry a different name, or use the 📍 Send My Location button.",
        "si": "❌ '{query}' සඳහා ස්ථාන හමු නොවීය.\n\nවෙනත් නමක් උත්සාහ කරන්න, හෝ 📍 මගේ ස්ථානය යවන්න බොත්තම භාවිתා කරන්න.",
    },
    "pickup_found": {
        "en": "📍 Found {n} pickup locations:\nChoose yours:",
        "si": "📍 ස්ථාන {n}ක් හමු විය:\nඔබේ ස්ථානය තෝරන්න:",
    },
    "dest_not_found": {
        "en": "❌ No destinations found for: {query}\n\nTry again or send location 📎",
        "si": "❌ '{query}' සඳහා ගමනාන්ත හමු නොවීය.\n\nනැවත උත්සාහ කරන්න හෝ ස්ථානය යවන්න 📎",
    },
    "dest_found": {
        "en": "🏁 Found {n} destinations:\nChoose yours:",
        "si": "🏁 ගමනාන්ත {n}ක් හමු විය:\nඔබේ ගමනාන්ত ස්ථානය තෝරන්න:",
    },
    "search_again": {
        "en": "🔍 Search Again",
        "si": "🔍 නැවත සොයන්න",
    },
    "ride_summary_header": {
        "en": "🎟️ *Your Ride Request*\n\n{veh} *Vehicle:* {label}\n📍 *Pickup:*  {pickup}\n🏁 *Drop-off:* {dropoff}\n📏 *Distance:* {dist} km{note}\n💰 *Fare Range:* {fare_range}\n\n⚠️ _Contact a driver before selecting_",
        "si": "🎟️ *ඔබගේ ගමන් ඉල්ලීම*\n\n{veh} *වාහනය:* {label}\n📍 *ලබාගැනීම:*  {pickup}\n🏁 *ගමනාන්ත:* {dropoff}\n📏 *දුර:* {dist} km{note}\n💰 *මිල පරාසය:* {fare_range}\n\n⚠️ _රියදුරෙකු තේරීමට පෙර සම්බන්ධ වන්න_",
    },
    "drivers_header": {
        "en": "🚗 *Available Drivers ({n}):*\n⚠️ Please contact a driver before selecting",
        "si": "🚗 *පවතින රියදුරන් ({n}):*\n⚠️ කරුණාකර රියදුරෙකු තෝරා ගැනීමට පෙර සම්බන්ධ වන්න",
    },

    # ── Driver registration ─────────────────────────────────────────────────────
    "drv_welcome_back": {
        "en": "👌 Welcome back, driver!\n\nPlease choose an action from the menu below 👇",
        "si": "👌 ආයුබෝවන්, රියදුරු!\n\nකරුණාකර පහත මෙනුවෙන් ක්‍රියාවක් තෝරන්න 👇",
    },
    "drv_reg_start": {
        "en": "🚗 Driver Registration\n\nWe need a few details to register you as a TeleCabs driver.\n\nStep 1/5 — Share your phone number:",
        "si": "🚗 රියදුරු ලියාපදිංචිය\n\nTeleCabs රියදුරෙකු ලෙස ලියාපදිංචි වීමට විස්තර කිහිපයක් අවශ්‍ය වේ.\n\nපියවර 1/5 — ඔබගේ දුරකතන අංකය බෙදාගන්න:",
    },
    "drv_phone_saved": {
        "en": "✅ Phone saved!\n\nStep 2/5 — Select your vehicle type:",
        "si": "✅ දුරකතන අංකය සුරකින ලදී!\n\nපියවර 2/5 — ඔබගේ වාහන වර්ගය තෝරන්න:",
    },
    "drv_vehicle_selected": {
        "en": "✅ {label} selected!\n\nStep 3/5 — Please enter your full name:",
        "si": "✅ {label} තෝරා ගන්නා ලදී!\n\nපියවර 3/5 — ඔබගේ සම්පූර්ණ නම ඇතුළත් කරන්න:",
    },
    "drv_name_saved": {
        "en": "✅ Name: {name}\n\nStep 4/5 — Enter vehicle number & model\n(e.g. CAB-1234, Prius)",
        "si": "✅ නම: {name}\n\nපියවර 4/5 — වාහන අංකය සහ ආකෘතිය ඇතුළත් කරන්න\n(උදා: CAB-1234, Prius)",
    },
    "drv_rate_prompt": {
        "en": "✅ {plate}\n\nStep 4.5/5 — Set your per-km rate (LKR)\n\nRiders will see YOUR rate when choosing a driver.\n\n💡 Current system rate: *{rate_emoji}* LKR/km\n_(Riders compare drivers by rate — enter yours or skip to use system rate)_\n\nType your rate (e.g. 100) or tap Skip:",
        "si": "✅ {plate}\n\nපියවර 4.5/5 — km ගාස්තුව සකසන්න (LKR)\n\nරියදුරෙකු තෝරන විට මගීන් ඔබේ ගාස්තුව දකිනු ඇත.\n\n💡 වත්මන් පද්ධති ගාස්තුව: *{rate_emoji}* LKR/km\n_(මගීන් ගාස්තුව අනුව රියදුරන් සැසඳිය — ඔබේ ගාස්තුව ඇතුළත් කරන්න හෝ Skip කරන්න)_\n\nඔබේ ගාස්තුව ටයිප් කරන්න (උදා: 100) හෝ Skip:",
    },
    "drv_skip_rate": {
        "en": "⏭ Skip (use system rate)",
        "si": "⏭ Skip (පද්ධති ගාස්තුව)",
    },
    "drv_invalid_rate": {
        "en": "⚠️ Please enter a positive number (e.g. 100) or skip:",
        "si": "⚠️ කරුණාකර ධනාත්මක සංඛ්‍යාවක් ඇතුළත් කරන්න (උදා: 100) හෝ Skip:",
    },
    "drv_rate_saved": {
        "en": "✅ Rate: {rate}\n\nStep 5/5 — Share your location 📍\nCheck-in when you move\n\nTap Next ▶️",
        "si": "✅ ගාස්තුව: {rate}\n\nපියවර 5/5 — ඔබේ ස්ථානය බෙදාගන්න 📍\nගමන් කරන විට Check-in කරන්න\n\nඊළඟ ▶️",
    },

    "drv_next_btn": {
        "en": "▶️ Next",
        "si": "▶️ ඊළඟ",
    },
    "drv_share_location": {
        "en": "📍 Share your current location to go online:",
        "si": "📍 Online වීමට ඔබේ දැනට ස්ථානය බෙදාගන්න:",
    },
    "drv_checkin_btn": {
        "en": "📍 Check-in",
        "si": "📍 Check-in",
    },
    "drv_registered": {
        "en": "🎉 You're registered and *ONLINE*!\n\n🚗 {name}\n📍 {plate}\n💰 Rate: {rate}\n\nRiders nearby will see you. Keep sharing your location to stay listed.",
        "si": "🎉 ඔබ ලියාපදිංචි වී *ONLINE* ය!\n\n🚗 {name}\n📍 {plate}\n💰 ගාස්තුව: {rate}\n\nළඟ සිටින මගීන් ඔබව දකිනු ඇත. Listed ව සිටීමට ස්ථානය බෙදාගැනීම දිගටම කරන්න.",
    },
    "drv_reset": {
        "en": "♻️ Your driver profile has been reset.\n\nStarting fresh registration...",
        "si": "♻️ ඔබේ රියදුරු ගිණුම ඉවත් කරන ලදී.\n\nනව ලියාපදිංචිය ආරම්භ කරමින්...",
    },

    # ── Trip notifications to rider ─────────────────────────────────────────────
    "ride_cancelled_by_driver": {
        "en": "❌ Driver cancelled Ride #{ride_id}.",
        "si": "❌ රියදුරා ගමන #{ride_id} අවලංගු කළේය.",
    },
    "ride_cancelled_by_rider": {
        "en": "❌ Rider cancelled Ride #{ride_id}.",
        "si": "❌ මගී ගමන #{ride_id} අවලංගු කළේය.",
    },

    # ── Pickup / Dest search UI ─────────────────────────────────────────────────
    "pickup_retry_prompt": {
        "en": "🔍 Type the pickup place name:",
        "si": "🔍 ලබාගැනීමේ ස්ථාන නාමය ටයිප් කරන්න:",
    },
    "dest_retry_prompt": {
        "en": "🔍 Type the destination name:\n(Example: Colombo, Kandy, Galle)",
        "si": "🔍 ගමනාන්ත නාමය ටයිප් කරන්න:\n(උදා: කොළඹ, මහනුවර, ගාල්ල)",
    },
    "pickup_set": {
        "en": "✅ Pickup set: {name}",
        "si": "✅ ලබාගැනීමේ ස්ථානය: {name}",
    },
    "dropoff_set": {
        "en": "✅ Drop-off set: {name}",
        "si": "✅ ගමනාන්ත ස්ථානය: {name}",
    },
    "invalid_selection": {
        "en": "⚠️ Invalid selection. Please try again.",
        "si": "⚠️ වැරදි තේරීමකි. කරුණාකර නැවත උත්සාහ කරන්න.",
    },
    "dest_not_found_tips": {
        "en": "❌ No results found for: {query}\n\nTips:\n• Type the name in English\n• Try a shorter name\n• Share location via 📎 attachment",
        "si": "❌ '{query}' සඳහා ප්‍රතිඵල නොමැත.\n\nඉඟි:\n• ඉංග්‍රීසියෙන් නම ටයිප් කරන්න\n• කෙටි නමක් භාවිතා කරන්න\n• 📎 attachment දෙකෙන් ස්ථානය යවන්න",
    },
    "dest_found_results": {
        "en": "📍 Found {n} results for \"{query}\":\nChoose your destination:",
        "si": "📍 \"{query}\" සඳහා ප්‍රතිඵල {n}ක් හමු විය:\nඔබේ ගමනාන්ත ස්ථානය තෝරන්න:",
    },

    # ── Driver card (in driver list) ────────────────────────────────────────────
    "drv_card_waiting": {
        "en": "⏳ Waiting for response…",
        "si": "⏳ ප්‍රතිචාරය බලාපොරොත්තු වෙමින්...",
    },
    "drv_card_available": {
        "en": "🟢 Available",
        "si": "🟢 ලබා ගත හැකිය",
    },
    "drv_card_new": {
        "en": "New",
        "si": "නව",
    },
    "btn_select_driver": {
        "en": "✅ Select",
        "si": "✅ තෝරන්න",
    },
    "btn_waiting": {
        "en": "⏳ Waiting…",
        "si": "⏳ බලාපොරොත්තු...",
    },

    # ── Rider summary / No drivers ──────────────────────────────────────────────
    "no_drivers_available": {
        "en": "⚠️ No drivers available nearby for {label} right now.\nPlease try again later.",
        "si": "⚠️ දැනට {label} සඳහා ළඟ රියදුරන් නොමැත.\nකරුණාකර පසුව නැවත උත්සාහ කරන්න.",
    },
    "ride_summary": {
        "en": (
            "🎟️ *Your Ride Request*\n\n"
            "{veh} *Vehicle:* {label}\n"
            "📍 *Pickup:* {pickup}\n"
            "🏁 *Drop-off:* {dropoff}\n"
            "✏ *Distance:* {dist} km{note}\n"
            "💰 *Est. Fare Range:* {fare_range}\n\n"
            "🚗 *Available Drivers ({n}):*\n"
            "⚠️ Please contact a driver before selecting"
        ),
        "si": (
            "🎟️ *ඔබගේ ගමන් ඉල්ලීම*\n\n"
            "{veh} *වාහනය:* {label}\n"
            "📍 *ලබාගැනීම:* {pickup}\n"
            "🏁 *ගමනාන්ත:* {dropoff}\n"
            "✏ *දුර:* {dist} km{note}\n"
            "💰 *ගෙවීම් පරාසය:* {fare_range}\n\n"
            "🚗 *පවතින රියදුරන් ({n}):*\n"
            "⚠️ කරුණාකර රියදුරෙකු සම්බන්ධ කිරීමෙන් පසු තෝරන්න"
        ),
    },

    # ── Contact driver reply ────────────────────────────────────────────────────
    "contact_wa_action": {
        "en": "💬 *WhatsApp Driver:*",
        "si": "💬 *රියදුරු WhatsApp කරන්න:*",
    },
    "contact_tg_action": {
        "en": "✈️ *Open Telegram chat with driver:*",
        "si": "✈️ *රියදුරු සමඟ Telegram chat විවෘත කරන්න:*",
    },
    "btn_open_whatsapp": {
        "en": "💬 Open WhatsApp",
        "si": "💬 WhatsApp විවෘත කරන්න",
    },
    "btn_open_telegram": {
        "en": "✈️ Open Telegram Chat",
        "si": "✈️ Telegram Chat",
    },
    "btn_whatsapp_driver": {
        "en": "💬 WhatsApp Driver",
        "si": "💬 රියදුරු WhatsApp",
    },

    # ── Trip start (rider message) ──────────────────────────────────────────────
    "trip_started_rider": {
        "en": "🟢 Your trip #{ride_id} has started!\n\nThe driver is on the way to your drop-off location.",
        "si": "🟢 ඔබගේ ගමන #{ride_id} ආරම්භ වී ඇත!\n\nරියදුරා ඔබගේ ගමනාන්ත ස්ථානය වෙත ළඟා වෙමින් සිටී.",
    },

    # ── Trip completion (rider message) ────────────────────────────────────────
    "trip_completed_rider": {
        "en": (
            "✅ TeleCabs — Trip #{ride_id} Completed!\n\n"
            "👤 Rider: {rider}\n"
            "{veh} Driver: {driver} {rating}\n"
            "🚘 Plate: {plate}\n"
            "📏 Distance: {dist} km\n"
            "💵 Rate: First {base_km} km = LKR {base_fare}, then LKR {per_km}/km\n"
            "{waiting}"
            "💰 Total Fare: LKR {fare}\n\n"
            "Thank you for using TeleCabs!"
        ),
        "si": (
            "✅ TeleCabs — ගමන #{ride_id} සම්පූර්ණ විය!\n\n"
            "👤 මගී: {rider}\n"
            "{veh} රියදුරු: {driver} {rating}\n"
            "🚘 Plate: {plate}\n"
            "📏 දුර: {dist} km\n"
            "💵 මිල: පළමු {base_km} km = LKR {base_fare}, ඉන්පසු LKR {per_km}/km\n"
            "{waiting}"
            "💰 මුළු ගෙවීම: LKR {fare}\n\n"
            "TeleCabs භාවිතා කිරීමට ස්තූතියි!"
        ),
    },

    # ── Rating ─────────────────────────────────────────────────────────────────
    "rate_driver_prompt": {
        "en": "Please rate your driver:",
        "si": "කරුණාකර ඔබගේ රියදුරු ශ්‍රේණිගත කරන්න:",
    },
    "rate_thanks": {
        "en": "Thank you for your {stars} ⭐️ rating!\n\n💬 Would you like to leave a comment?\n(Tell us anything — good or bad)\n\nType your comment below, or tap Skip:",
        "si": "ඔබගේ {stars} ⭐️ ශ්‍රේණිගත කිරීමට ස්තූතියි!\n\n💬 අදහස් දැක්වීමට කැමතිද?\n(හොඳ හෝ නරක ඕනෑ දෙයක් කියන්න)\n\nඅදහස ටයිප් කරන්න, නැතිනම් Skip:",
    },
    "rate_submitted": {
        "en": "✅ Rating submitted. Thank you!",
        "si": "✅ ශ්‍රේණිගත කිරීම ලබා ගන්නා ලදී. ස්තූතියි!",
    },
    "rate_feedback_thanks": {
        "en": "✅ Thank you for your feedback!\n\n📝 Your comment has been recorded.",
        "si": "✅ ඔබගේ අදහසට ස්තූතියි!\n\n📝 ඔබේ අදහස සටහන් කරන ලදී.",
    },
    "btn_skip": {
        "en": "➡️ Skip",
        "si": "➡️ Skip",
    },

    # ── Driver dashboard ────────────────────────────────────────────────────────
    "drv_dashboard": {
        "en": "🚗 Driver Dashboard — Choose an action 👇",
        "si": "🚗 රියදුරු Dashboard — ක්‍රියාවක් තෝරන්න 👇",
    },
    "drv_location_updated": {
        "en": "👌 Location updated\n\nIf wrong, check-in again or send via 📎 Location",
        "si": "👌 ස්ථානය යාවත්කාලීන කරන ලදී\n\nවැරදි නම් නැවත Check-in කරන්න හෝ 📎 Location ඔස්සේ යවන්න",
    },
    "drv_muted": {
        "en": "🔕 Muted. You will NOT receive ride notifications until you unmute.",
        "si": "🔕 Muted. Unmute කරන තෙක් ඔබට ගමන් දැනුම්දීම් ලැබෙන්නේ නැත.",
    },
    "drv_unmuted": {
        "en": "🔔 Unmuted! You will now receive nearby ride requests.",
        "si": "🔔 Unmuted! දැන් ළඟ ගමන් ඉල්ලීම් ලැබෙනු ඇත.",
    },
    "drv_not_registered": {
        "en": "⚠️ You're not registered as a driver.",
        "si": "⚠️ ඔබ රියදුරෙකු ලෙස ලියාපදිංචි වී නොමැත.",
    },
    "drv_update_location_prompt": {
        "en": "Share your current location to update your position:",
        "si": "ඔබේ ස්ථානය යාවත්කාලීන කිරීමට දැනට ස්ථානය බෙදාගන්න:",
    },
    "btn_send_location_drv": {
        "en": "📍 Send Location",
        "si": "📍 ස්ථානය යවන්න",
    },
    "drv_rate_menu": {
        "en": "💰 *My Per-Km Rate*\n\n{rate_info}\n\nEnter your new rate (e.g. *120*) or tap below:",
        "si": "💰 *මගේ km ගාස්තුව*\n\n{rate_info}\n\nනව ගාස්තුව ඇතුළත් කරන්න (උදා: *120*) හෝ tap කරන්න:",
    },
    "drv_current_rate": {
        "en": "Your current rate: *LKR {rate}/km*",
        "si": "ඔබේ දැනට ගාස්තුව: *LKR {rate}/km*",
    },
    "drv_using_system_rate": {
        "en": "You are using the *system rate: LKR {rate}/km*",
        "si": "ඔබ *පද්ධති ගාස්තුව: LKR {rate}/km* භාවිතා කරයි",
    },
    "btn_keep_rate": {
        "en": "↩️ Keep Current Rate",
        "si": "↩️ දැනට ගාස්තුව රඳවා ගන්න",
    },
    "btn_system_rate": {
        "en": "🔄 Use System Rate",
        "si": "🔄 පද්ධති ගාස්තුව",
    },
    "drv_rate_unchanged": {
        "en": "✅ Rate unchanged.",
        "si": "✅ ගාස්තුව වෙනස් නොකෙරිණි.",
    },
    "drv_rate_reset": {
        "en": "✅ Reset to system rate. Riders will see the system price.",
        "si": "✅ පද්ධති ගාස්තුවට නැවත සකසන ලදී. මගීන් පද්ධති මිල දකිනු ඇත.",
    },
    "drv_rate_updated": {
        "en": "✅ Your per-km rate updated to *LKR {rate}/km*\n\nRiders will see this rate in the driver list.",
        "si": "✅ ඔබේ km ගාස්තුව *LKR {rate}/km* ලෙස යාවත්කාලීන කරන ලදී.\n\nමගීන් රියදුරු ලැයිස්තුවේ මෙම ගාස්තුව දකිනු ඇත.",
    },
    "drv_rate_invalid": {
        "en": "⚠️ Invalid number. Enter a rate like *120* or tap the buttons below:",
        "si": "⚠️ වැරදි සංඛ්‍යාවකි. *120* වැනි ගාස්තුවක් ඇතුළත් කරන්න හෝ tap:",
    },
    "drv_rate_positive": {
        "en": "⚠️ Rate must be a positive number (e.g. 100). Try again:",
        "si": "⚠️ ගාස්තුව ධනාත්මක සංඛ්‍යාවක් විය යුතුය (උදා: 100). නැවත උත්සාහ කරන්න:",
    },

    # ── End trip flow ───────────────────────────────────────────────────────────
    "end_trip_no_active": {
        "en": "⚠️ No active trip found.",
        "si": "⚠️ සක්‍රිය ගමනක් හමු නොවිණි.",
    },
    "end_trip_prompt": {
        "en": (
            "🛑 Ending Trip #{ride_id}\n\n"
            "📍 GPS tracked distance: {gps} km\n\n"
            "📏 Enter total kilometers from your *vehicle meter*:\n"
            "(Example: 5.2)\n\n"
            "Or type `gps` to use GPS distance."
        ),
        "si": (
            "🛑 ගමන #{ride_id} අවසන් කිරීම\n\n"
            "📍 GPS ලුහු දුර: {gps} km\n\n"
            "📏 *වාහන මීටරයේ* සම්පූර්ණ km ඇතුළත් කරන්න:\n"
            "(උදා: 5.2)\n\n"
            "GPS දුර සඳහා `gps` ටයිප් කරන්න."
        ),
    },
    "end_trip_dist_set": {
        "en": "✅ Distance set: {dist} km\n\n⏱ Enter *waiting time* in minutes (or `0` for none):\n(Example: 3)",
        "si": "✅ දුර සකසා ඇත: {dist} km\n\n⏱ *රැඳී සිටි කාලය* මිනිත්තු ඇතුළත් කරන්න (නැතිනම් `0`):\n(උදා: 3)",
    },
    "end_trip_invalid_dist": {
        "en": "⚠️ Please enter a valid number (e.g., 5.2) or type `gps`.",
        "si": "⚠️ වලංගු සංඛ්‍යාවක් ඇතුළත් කරන්න (උදා: 5.2) හෝ `gps` ටයිප් කරන්න.",
    },
    "end_trip_positive": {
        "en": "⚠️ Please enter a positive number.",
        "si": "⚠️ ධනාත්මක සංඛ්‍යාවක් ඇතුළත් කරන්න.",
    },
    "end_trip_invalid_wait": {
        "en": "⚠️ Please enter a valid number (e.g., 3).",
        "si": "⚠️ වලංගු සංඛ්‍යාවක් ඇතුළත් කරන්න (උදා: 3).",
    },
    "end_trip_no_active_wait": {
        "en": "⚠️ No active trip found.",
        "si": "⚠️ සක්‍රිය ගමනක් හමු නොවිණි.",
    },
    "back_to_menu": {
        "en": "Welcome back! 🚕\n\nFast and simple taxi service.",
        "si": "ආයුබෝවන්! 🚕\n\nශීඝ්‍ර හා සරල ටැක්සි සේවාව.",
    },
}




def t(key: str, lang: str, **kwargs) -> str:
    """
    Translate key to lang. Falls back to English if key/lang missing.
    kwargs are used for f-string style substitution.
    """
    lang = lang if lang in SUPPORTED else DEFAULT
    text = _T.get(key, {}).get(lang) or _T.get(key, {}).get(DEFAULT, f"[{key}]")
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


async def get_lang(user_id: int) -> str:
    """Fetch user's preferred language from DB. Returns 'en' if not set."""
    row = await db.get_user(user_id)
    if row and row.get("language"):
        return row["language"]
    return DEFAULT
