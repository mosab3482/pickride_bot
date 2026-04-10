from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CommandHandler, CallbackQueryHandler, filters
)

import database as db
from config import ADMIN_IDS
from handlers.start import main_keyboard
from utils.distance import METHOD_LABELS, METHOD_DESCRIPTIONS
from utils.fare import VEHICLE_TYPES, VEHICLE_EMOJIS


async def is_admin(user_id: int) -> bool:
    """Check if user is admin (from .env OR from DB)."""
    if user_id in ADMIN_IDS:
        return True
    return await db.is_db_admin(user_id)


def is_super_admin(user_id: int) -> bool:
    """Check if user is a super admin (from .env only). Only super admins can add/remove admins."""
    return user_id in ADMIN_IDS


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Pricing Settings",        callback_data="adm_pricing")],
        [InlineKeyboardButton("🚗 Vehicle Pricing",          callback_data="adm_vehpricing")],
        [InlineKeyboardButton("📍 System Settings",         callback_data="adm_system")],
        [InlineKeyboardButton("🗺️ Distance Method",         callback_data="adm_distance")],
        [InlineKeyboardButton("🚫 Category Control",        callback_data="adm_category")],
        [InlineKeyboardButton("👤 User Management",         callback_data="adm_users")],
        [InlineKeyboardButton("👑 Admin Management",        callback_data="adm_adminmgmt")],
        [InlineKeyboardButton("🚖 Driver List",             callback_data="adm_drivers"),
         InlineKeyboardButton("🚶 Rider List",               callback_data="adm_riders")],
        [InlineKeyboardButton("👥 All Users",               callback_data="adm_allusers")],
        [InlineKeyboardButton("📊 Trip Stats",              callback_data="adm_trips"),
         InlineKeyboardButton("💵 Revenue",                  callback_data="adm_revenue")],
        [InlineKeyboardButton("🧹 Clean Cache",             callback_data="adm_cleancache")],
        [InlineKeyboardButton("🧾 Who Am I",                callback_data="adm_whoami"),
         InlineKeyboardButton("🆔 Group ID",                 callback_data="adm_groupid")],
    ])


def pricing_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 Set Base Fare",     callback_data="adm_setbase")],
        [InlineKeyboardButton("📏 Set Per-KM Rate",   callback_data="adm_setrate")],
        [InlineKeyboardButton("🛣️ Set Base KM",       callback_data="adm_setbasekm")],
        [InlineKeyboardButton("⏱ Set Waiting Rate",   callback_data="adm_setwaitrate")],
        [InlineKeyboardButton("🚗 Vehicle Pricing →",  callback_data="adm_vehpricing")],
        [InlineKeyboardButton("⬅️ Back",              callback_data="adm_back")],
    ])


async def vehicle_pricing_keyboard() -> InlineKeyboardMarkup:
    """Show all vehicle types with their current rates."""
    global_base   = float(await db.get_setting("base_fare")    or 100)
    global_rate   = float(await db.get_setting("per_km_rate")  or 50)
    global_basekm = float(await db.get_setting("base_km")      or 2)
    global_wait   = float(await db.get_setting("waiting_rate") or 5)

    rows = []
    for vt in VEHICLE_TYPES:
        emoji  = VEHICLE_EMOJIS.get(vt, "🚗")
        b_raw  = await db.get_setting(f"base_fare_{vt}")
        r_raw  = await db.get_setting(f"per_km_rate_{vt}")
        k_raw  = await db.get_setting(f"base_km_{vt}")
        w_raw  = await db.get_setting(f"waiting_rate_{vt}")
        b_val  = float(b_raw) if b_raw else global_base
        r_val  = float(r_raw) if r_raw else global_rate
        k_val  = float(k_raw) if k_raw else global_basekm
        w_val  = float(w_raw) if w_raw else global_wait
        custom = "✅" if (b_raw or r_raw or k_raw or w_raw) else "🔗"
        label  = f"{custom} {emoji} {vt.title()} — {b_val}+{r_val}/km | {k_val}km | w:{w_val}"
        rows.append([InlineKeyboardButton(label, callback_data=f"adm_veh_{vt}")])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="adm_back")])
    return InlineKeyboardMarkup(rows)


def vehicle_edit_keyboard(vt: str) -> InlineKeyboardMarkup:
    """Edit keyboard for a specific vehicle type — all 4 pricing fields."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Set Base Fare",      callback_data=f"adm_setvbase_{vt}")],
        [InlineKeyboardButton("📏 Set Per-KM Rate",    callback_data=f"adm_setvrate_{vt}")],
        [InlineKeyboardButton("🛣️ Set Base KM",        callback_data=f"adm_setvbasekm_{vt}")],
        [InlineKeyboardButton("⏱ Set Waiting Rate",   callback_data=f"adm_setvwait_{vt}")],
        [InlineKeyboardButton("🔄 Reset to Global",    callback_data=f"adm_resetveh_{vt}")],
        [InlineKeyboardButton("⬅️ Back",               callback_data="adm_vehpricing")],
    ])



def system_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Set Driver Radius",  callback_data="adm_setradius")],
        [InlineKeyboardButton("⬅️ Back",               callback_data="adm_back")],
    ])


def category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Disable Category",   callback_data="adm_blockcat")],
        [InlineKeyboardButton("✅ Enable Category",    callback_data="adm_unblockcat")],
        [InlineKeyboardButton("⬅️ Back",               callback_data="adm_back")],
    ])


def distance_keyboard(current: str) -> InlineKeyboardMarkup:
    """Build distance method selection keyboard. Active method shows ✅."""
    def _btn(method: str, label: str) -> InlineKeyboardButton:
        tick = "✅ " if current == method else ""
        return InlineKeyboardButton(f"{tick}{label}", callback_data=f"adm_setmethod_{method}")

    return InlineKeyboardMarkup([
        [_btn("google",    "🌐 Google Maps API")],
        [_btn("osrm",      "🗺️ OSRM (Free Routing)")],
        [_btn("haversine", "📐 Haversine (Offline)")],
        [InlineKeyboardButton("⬅️ Back", callback_data="adm_back")],
    ])


def user_mgmt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⛔ Block User",         callback_data="adm_blockuser")],
        [InlineKeyboardButton("✅ Unblock User",       callback_data="adm_unblockuser")],
        [InlineKeyboardButton("⬅️ Back",               callback_data="adm_back")],
    ])


def admin_mgmt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Admin",          callback_data="adm_addadmin")],
        [InlineKeyboardButton("➖ Remove Admin",       callback_data="adm_removeadmin")],
        [InlineKeyboardButton("📋 Admin List",         callback_data="adm_listadmins")],
        [InlineKeyboardButton("⬅️ Back",               callback_data="adm_back")],
    ])


# ─────────────────────────────────────────────
#  Entry — Admin Control button
# ─────────────────────────────────────────────
async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "👑 *Admin Control Panel*\n\nSelect an option:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard(),
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(update.effective_user.id):
        await query.answer("⛔ Access denied.", show_alert=True)
        return
    await query.answer()
    data = query.data

    # ── Navigation ──────────────────────────────
    if data == "adm_back":
        await query.edit_message_text(
            "👑 *Admin Control Panel*\n\nSelect an option:",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard(),
        )

    elif data == "adm_pricing":
        base   = await db.get_setting("base_fare")
        rate   = await db.get_setting("per_km_rate")
        basekm = await db.get_setting("base_km")
        waitrt = await db.get_setting("waiting_rate")
        await query.edit_message_text(
            f"💰 *Pricing Settings*\n\n"
            f"Base Fare: LKR {base}\n"
            f"Per-KM Rate: LKR {rate}\n"
            f"Base KM: {basekm} km\n"
            f"Waiting Rate: LKR {waitrt}/min\n\n"
            f"Select what to change:",
            parse_mode="Markdown",
            reply_markup=pricing_keyboard(),
        )

    elif data == "adm_system":
        radius = await db.get_setting("driver_radius")
        await query.edit_message_text(
            f"📍 *System Settings*\n\nDriver Search Radius: {radius} km",
            parse_mode="Markdown",
            reply_markup=system_keyboard(),
        )

    elif data == "adm_category":
        blocked = await db.get_blocked_categories()
        blocked_str = ", ".join(blocked) if blocked else "None"
        await query.edit_message_text(
            f"🚫 *Category Control*\n\nBlocked: {blocked_str}",
            parse_mode="Markdown",
            reply_markup=category_keyboard(),
        )

    elif data == "adm_vehpricing":
        global_base = await db.get_setting("base_fare")   or "100"
        global_rate = await db.get_setting("per_km_rate") or "50"
        await query.edit_message_text(
            f"🚗 *Vehicle Pricing*\n\n"
            f"🔗 = Using global rate\n"
            f"✅ = Custom rate set\n\n"
            f"*Global defaults:*\n"
            f"Base Fare: LKR {global_base}\n"
            f"Per-KM Rate: LKR {global_rate}/km\n\n"
            f"Tap a vehicle to set custom pricing:",
            parse_mode="Markdown",
            reply_markup=await vehicle_pricing_keyboard(),
        )

    elif data.startswith("adm_veh_") and not data.startswith("adm_setvbase_") \
            and not data.startswith("adm_setvrate_") and not data.startswith("adm_resetveh_") \
            and not data.startswith("adm_setvbasekm_") and not data.startswith("adm_setvwait_"):
        vt = data.replace("adm_veh_", "").lower()
        if vt not in VEHICLE_TYPES:
            await query.answer("⚠️ Unknown vehicle type.", show_alert=True)
            return
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        global_base   = float(await db.get_setting("base_fare")    or 100)
        global_rate   = float(await db.get_setting("per_km_rate")  or 50)
        global_basekm = float(await db.get_setting("base_km")      or 2)
        global_wait   = float(await db.get_setting("waiting_rate") or 5)
        b_raw  = await db.get_setting(f"base_fare_{vt}")
        r_raw  = await db.get_setting(f"per_km_rate_{vt}")
        k_raw  = await db.get_setting(f"base_km_{vt}")
        w_raw  = await db.get_setting(f"waiting_rate_{vt}")
        b_val  = float(b_raw) if b_raw else global_base
        r_val  = float(r_raw) if r_raw else global_rate
        k_val  = float(k_raw) if k_raw else global_basekm
        w_val  = float(w_raw) if w_raw else global_wait
        status = "✅ Custom set" if (b_raw or r_raw or k_raw or w_raw) else "🔗 Using global"
        await query.edit_message_text(
            f"{emoji} *{vt.title()} Pricing*\n\n"
            f"Status: {status}\n\n"
            f"💰 Base Fare:    LKR {b_val}\n"
            f"📏 Per-KM Rate:  LKR {r_val}/km\n"
            f"🛣️ Base KM:      {k_val} km\n"
            f"⏱ Waiting Rate: LKR {w_val}/min\n\n"
            f"*(Global: LKR {global_base} base | LKR {global_rate}/km | {global_basekm} km | LKR {global_wait}/min)*\n\n"
            f"Tap to edit:",
            parse_mode="Markdown",
            reply_markup=vehicle_edit_keyboard(vt),
        )

    elif data.startswith("adm_setvbase_"):
        vt = data.replace("adm_setvbase_", "").lower()
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        context.user_data["adm_awaiting"]   = f"vbase_{vt}"
        context.user_data["adm_veh_back"]   = vt
        await query.edit_message_text(
            f"{emoji} *{vt.title()} — Base Fare*\n\n"
            f"Enter the new base fare (LKR):",
            parse_mode="Markdown",
        )

    elif data.startswith("adm_setvrate_"):
        vt = data.replace("adm_setvrate_", "").lower()
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        context.user_data["adm_awaiting"]   = f"vrate_{vt}"
        context.user_data["adm_veh_back"]   = vt
        await query.edit_message_text(
            f"{emoji} *{vt.title()} — Per-KM Rate*\n\n"
            f"Enter the new per-km rate (LKR):",
            parse_mode="Markdown",
        )

    elif data.startswith("adm_setvbasekm_"):
        vt = data.replace("adm_setvbasekm_", "").lower()
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        context.user_data["adm_awaiting"] = f"vbasekm_{vt}"
        context.user_data["adm_veh_back"] = vt
        global_basekm = await db.get_setting("base_km") or "2"
        await query.edit_message_text(
            f"{emoji} *{vt.title()} — Base KM*\n\n"
            f"Global default: {global_basekm} km\n\n"
            f"Enter new Base KM (free distance before per-km rate kicks in):",
            parse_mode="Markdown",
        )

    elif data.startswith("adm_setvwait_"):
        vt = data.replace("adm_setvwait_", "").lower()
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        context.user_data["adm_awaiting"] = f"vwait_{vt}"
        context.user_data["adm_veh_back"] = vt
        global_wait = await db.get_setting("waiting_rate") or "5"
        await query.edit_message_text(
            f"{emoji} *{vt.title()} — Waiting Rate*\n\n"
            f"Global default: LKR {global_wait}/min\n\n"
            f"Enter new Waiting Rate (LKR per minute):",
            parse_mode="Markdown",
        )

    elif data.startswith("adm_resetveh_"):
        vt = data.replace("adm_resetveh_", "").lower()
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        # Delete all 4 custom rates → fall back to global
        await db.set_setting(f"base_fare_{vt}",    "")
        await db.set_setting(f"per_km_rate_{vt}",  "")
        await db.set_setting(f"base_km_{vt}",      "")
        await db.set_setting(f"waiting_rate_{vt}", "")
        await query.edit_message_text(
            f"✅ {emoji} *{vt.title()}* — all 4 rates reset to global defaults.",
            parse_mode="Markdown",
            reply_markup=await vehicle_pricing_keyboard(),
        )


    elif data == "adm_distance":
        from config import GOOGLE_MAPS_API_KEY as _gkey
        current  = (await db.get_setting("distance_method") or "osrm").lower()
        label    = METHOD_LABELS.get(current, current)
        desc     = METHOD_DESCRIPTIONS.get(current, "")
        google_key = "✅ Set" if _gkey else "❌ Not set"
        # Inform admin if Google is auto-selected
        auto_note = ""
        if _gkey and current != "haversine":
            auto_note = "\n⚡ *Google API key detected — Google is used automatically for best accuracy.*"
        await query.edit_message_text(
            f"🗺️ *Distance Calculation Method*\n\n"
            f"*Saved setting:* {label}\n"
            f"📝 {desc}\n\n"
            f"🔑 Google API Key: {google_key}{auto_note}\n\n"
            f"Tap a method below to change the saved setting:",
            parse_mode="Markdown",
            reply_markup=distance_keyboard(current),
        )

    elif data.startswith("adm_setmethod_"):
        method = data.replace("adm_setmethod_", "").lower()
        if method not in ("google", "osrm", "haversine"):
            await query.answer("⚠️ Invalid method.", show_alert=True)
            return
        # Block google if no API key
        if method == "google" and not __import__('config').GOOGLE_MAPS_API_KEY:
            await query.answer(
                "⚠️ Google Maps API key is not set!\nAdd GOOGLE_MAPS_API_KEY to your .env file.",
                show_alert=True,
            )
            return
        await db.set_setting("distance_method", method)
        # Clear route cache so next requests use the new method
        await db.cleanup_all_cache()
        label = METHOD_LABELS.get(method, method)
        desc  = METHOD_DESCRIPTIONS.get(method, "")
        await query.edit_message_text(
            f"✅ *Distance method switched!*\n\n"
            f"*New method:* {label}\n"
            f"📝 {desc}\n\n"
            f"🧹 Route cache cleared — all new fares will use this method.",
            parse_mode="Markdown",
            reply_markup=distance_keyboard(method),
        )


    elif data == "adm_users":
        await query.edit_message_text(
            "👤 *User Management*",
            parse_mode="Markdown",
            reply_markup=user_mgmt_keyboard(),
        )

    # ── Admin Management ────────────────────────
    elif data == "adm_adminmgmt":
        if not is_super_admin(update.effective_user.id):
            await query.edit_message_text(
                "⛔ Only *Super Admins* (from .env) can manage admins.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]),
            )
            return

        db_admins = await db.get_all_admins()
        count = len(db_admins)
        env_count = len(ADMIN_IDS)
        await query.edit_message_text(
            f"👑 *Admin Management*\n\n"
            f"🔒 Super Admins (env): {env_count}\n"
            f"➕ Added Admins (DB): {count}\n\n"
            f"Super Admins can add/remove other admins.",
            parse_mode="Markdown",
            reply_markup=admin_mgmt_keyboard(),
        )

    elif data == "adm_addadmin":
        if not is_super_admin(update.effective_user.id):
            await query.edit_message_text("⛔ Super Admin access required.")
            return
        context.user_data["adm_awaiting"] = "add_admin"
        await query.edit_message_text(
            "➕ Enter the *Telegram User ID* to add as admin:\n\n"
            "💡 The user can find their ID by messaging @userinfobot",
            parse_mode="Markdown",
        )

    elif data == "adm_removeadmin":
        if not is_super_admin(update.effective_user.id):
            await query.edit_message_text("⛔ Super Admin access required.")
            return
        context.user_data["adm_awaiting"] = "remove_admin"
        await query.edit_message_text(
            "➖ Enter the *Telegram User ID* to remove from admins:",
            parse_mode="Markdown",
        )

    elif data == "adm_listadmins":
        db_admins = await db.get_all_admins()
        lines = []

        # Show env super admins
        for aid in ADMIN_IDS:
            user = await db.get_user(aid)
            name = f"@{user['username']}" if user and user["username"] else str(aid)
            lines.append(f"🔒 {name} (ID: `{aid}`) — Super Admin")

        # Show DB admins
        for a in db_admins:
            user = await db.get_user(a["user_id"])
            name = f"@{user['username']}" if user and user["username"] else str(a["user_id"])
            added = str(a["added_at"])[:10] if a["added_at"] else "N/A"
            lines.append(f"👑 {name} (ID: `{a['user_id']}`) — Added: {added}")

        if not lines:
            text = "📋 *Admin List*\n\nNo admins configured."
        else:
            text = "📋 *Admin List*\n\n" + "\n".join(lines)

        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_adminmgmt")]]),
        )

    # ── Data queries ────────────────────────────
    elif data == "adm_drivers":
        drivers = await db.get_all_drivers()
        if not drivers:
            text = "No drivers registered."
        else:
            lines = []
            for d in drivers[:20]:
                uname = f"@{d['username']}" if d["username"] else d["first_name"]
                stars = f"{d['rating_sum']/d['rating_count']:.1f}⭐" if d["rating_count"] else "No ratings"
                status = "🟢" if d["is_online"] else "🔴"
                lines.append(f"{status} {uname} | {d['vehicle_type']} | {d['plate_number']} | {stars}")
            text = "🚖 *Drivers List*\n\n" + "\n".join(lines)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]))

    elif data == "adm_riders":
        riders = await db.get_all_riders()
        if not riders:
            text = "No riders yet."
        else:
            lines = [f"@{r['username'] or r['first_name']} | Joined: {str(r['created_at'])[:10]}" for r in riders[:20]]
            text = "🚶 *Riders List*\n\n" + "\n".join(lines)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]))

    elif data == "adm_allusers":
        users = await db.get_all_users()
        lines = [f"{'🔴' if u['is_blocked'] else '🟢'} {u['username'] or u['first_name']} | {u['role']}" for u in users[:20]]
        text = "👥 *All Users*\n\n" + ("\n".join(lines) if lines else "No users.")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]))

    elif data == "adm_trips":
        stats = await db.get_trip_stats()
        text = (
            f"📊 *Trip Statistics*\n\n"
            f"✅ Completed:   {stats['completed']}\n"
            f"❌ Cancelled:   {stats['cancelled']}\n"
            f"⏳ Pending:     {stats['pending']}\n"
            f"🟢 In Progress: {stats['in_progress']}\n"
            f"📦 Total:       {stats['total']}"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]))

    elif data == "adm_revenue":
        stats = await db.get_trip_stats()
        text = (
            f"💵 *Revenue Summary*\n\n"
            f"✅ Completed Rides: {stats['completed']}\n"
            f"💰 Total Revenue:   LKR {stats['total_revenue']:.2f}"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]))

    elif data == "adm_cleancache":
        await db.cleanup_expired_cache()
        await query.edit_message_text(
            "🧹 Route cache cleaned! Expired entries removed.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]),
        )

    elif data == "adm_whoami":
        u = update.effective_user
        admin_type = "🔒 Super Admin" if is_super_admin(u.id) else "👑 Admin"
        text = f"🧾 *Who Am I*\n\nName: {u.full_name}\nID: `{u.id}`\nUsername: @{u.username}\nRole: {admin_type}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]))

    elif data == "adm_groupid":
        chat = update.effective_chat
        text = f"🆔 *Chat Info*\n\nChat ID: `{chat.id}`\nType: {chat.type}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]))

    # ── Input prompts ───────────────────────────
    elif data == "adm_setbase":
        context.user_data["adm_awaiting"] = "base_fare"
        await query.edit_message_text("💰 Enter the new *Base Fare* (LKR):", parse_mode="Markdown")

    elif data == "adm_setrate":
        context.user_data["adm_awaiting"] = "per_km_rate"
        await query.edit_message_text("📏 Enter the new *Per-KM Rate* (LKR):", parse_mode="Markdown")

    elif data == "adm_setbasekm":
        context.user_data["adm_awaiting"] = "base_km"
        await query.edit_message_text("🛣️ Enter the new *Base KM*:", parse_mode="Markdown")

    elif data == "adm_setwaitrate":
        context.user_data["adm_awaiting"] = "waiting_rate"
        await query.edit_message_text("⏱ Enter the new *Waiting Rate* (LKR per minute):", parse_mode="Markdown")

    elif data == "adm_setradius":
        context.user_data["adm_awaiting"] = "driver_radius"
        await query.edit_message_text("📡 Enter the new *Driver Search Radius* (km):", parse_mode="Markdown")

    elif data == "adm_blockcat":
        context.user_data["adm_awaiting"] = "block_cat"
        await query.edit_message_text(
            "🚫 Enter vehicle type to *disable*:\n"
            "`bike` / `tuk` / `car` / `minivan` / `van` / `bus`",
            parse_mode="Markdown",
        )

    elif data == "adm_unblockcat":
        context.user_data["adm_awaiting"] = "unblock_cat"
        await query.edit_message_text(
            "✅ Enter vehicle type to *enable*:\n"
            "`bike` / `tuk` / `car` / `minivan` / `van` / `bus`",
            parse_mode="Markdown",
        )

    elif data == "adm_blockuser":
        context.user_data["adm_awaiting"] = "block_user"
        await query.edit_message_text(
            "⛔ Enter *User ID*, *@username*, or *name* to block:",
            parse_mode="Markdown",
        )

    elif data == "adm_unblockuser":
        context.user_data["adm_awaiting"] = "unblock_user"
        await query.edit_message_text(
            "✅ Enter *User ID*, *@username*, or *name* to unblock:",
            parse_mode="Markdown",
        )


async def admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for admin settings."""
    if not await is_admin(update.effective_user.id):
        return
    awaiting = context.user_data.get("adm_awaiting")
    if not awaiting:
        return

    text = update.message.text.strip()
    context.user_data.pop("adm_awaiting")

    if awaiting in ("base_fare", "per_km_rate", "base_km", "driver_radius", "waiting_rate"):
        try:
            float(text)
        except ValueError:
            await update.message.reply_text("⚠️ Please enter a valid number.")
            return
        await db.set_setting(awaiting, text)
        labels = {
            "base_fare":     "Base Fare",
            "per_km_rate":   "Per-KM Rate",
            "base_km":       "Base KM",
            "waiting_rate":  "Waiting Rate (per min)",
            "driver_radius": "Driver Search Radius",
        }
        await update.message.reply_text(f"✅ *{labels[awaiting]}* updated to `{text}`.", parse_mode="Markdown")

    elif awaiting.startswith("vbase_") or awaiting.startswith("vrate_") \
            or awaiting.startswith("vbasekm_") or awaiting.startswith("vwait_"):
        try:
            val = float(text)
            if val < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Please enter a valid positive number.")
            return

        if awaiting.startswith("vbase_"):
            vt  = awaiting.replace("vbase_", "")
            key = f"base_fare_{vt}"
            lbl = "Base Fare"
        elif awaiting.startswith("vrate_"):
            vt  = awaiting.replace("vrate_", "")
            key = f"per_km_rate_{vt}"
            lbl = "Per-KM Rate"
        elif awaiting.startswith("vbasekm_"):
            vt  = awaiting.replace("vbasekm_", "")
            key = f"base_km_{vt}"
            lbl = "Base KM"
        else:  # vwait_
            vt  = awaiting.replace("vwait_", "")
            key = f"waiting_rate_{vt}"
            lbl = "Waiting Rate"

        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        await db.set_setting(key, text)
        suffix = " km" if lbl == "Base KM" else " LKR"
        unit   = "km" if lbl == "Base KM" else ("LKR/min" if lbl == "Waiting Rate" else "LKR")
        await update.message.reply_text(
            f"✅ {emoji} *{vt.title()} — {lbl}* set to `{text} {unit}`.",
            parse_mode="Markdown",
        )


    elif awaiting == "block_cat":
        vt = text.lower()
        if vt not in VEHICLE_TYPES:
            await update.message.reply_text(
                "⚠️ Invalid category. Valid types: bike, tuk, car, minivan, van, bus"
            )
            return
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        await db.block_category(vt)
        await update.message.reply_text(
            f"🚫 {emoji} *{vt.title()}* has been disabled.", parse_mode="Markdown"
        )

    elif awaiting == "unblock_cat":
        vt = text.lower()
        if vt not in VEHICLE_TYPES:
            await update.message.reply_text(
                "⚠️ Invalid category. Valid types: bike, tuk, car, minivan, van, bus"
            )
            return
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        await db.unblock_category(vt)
        await update.message.reply_text(
            f"✅ {emoji} *{vt.title()}* has been enabled.", parse_mode="Markdown"
        )

    elif awaiting in ("block_user", "unblock_user"):
        blocking = awaiting == "block_user"
        uid = None
        user_row = None

        # 1) Try numeric ID first
        try:
            uid = int(text.lstrip("@"))
            user_row = await db.get_user(uid)
        except ValueError:
            pass

        # 2) Try @username lookup
        if uid is None:
            user_row = await db.get_user_by_username(text)
            if user_row:
                uid = user_row["user_id"]

        # 3) Try first-name search
        if uid is None:
            matches = await db.get_users_by_name(text)
            if len(matches) == 1:
                user_row = matches[0]
                uid = user_row["user_id"]
            elif len(matches) > 1:
                lines = [
                    f"• {m['first_name']} (@{m['username'] or '—'}) → `{m['user_id']}`"
                    for m in matches[:10]
                ]
                await update.message.reply_text(
                    f"⚠️ Found {len(matches)} users matching *{text}*. "
                    f"Please re-enter with the exact ID:\n\n" + "\n".join(lines),
                    parse_mode="Markdown",
                )
                context.user_data["adm_awaiting"] = awaiting  # keep waiting
                return

        if uid is None:
            await update.message.reply_text(
                f"⚠️ No user found for `{text}`. Try their numeric ID instead.",
                parse_mode="Markdown",
            )
            return

        await db.block_user(uid, blocking)
        name = (
            f"@{user_row['username']}" if user_row and user_row["username"]
            else (user_row["first_name"] if user_row else str(uid))
        )
        if blocking:
            await update.message.reply_text(
                f"⛔ *{name}* (`{uid}`) has been blocked.", parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"✅ *{name}* (`{uid}`) has been unblocked.", parse_mode="Markdown"
            )

    elif awaiting == "add_admin":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("⚠️ Enter a valid numeric User ID.")
            return
        if uid in ADMIN_IDS:
            await update.message.reply_text("ℹ️ This user is already a Super Admin (from .env).")
            return
        await db.add_admin(uid, update.effective_user.id)
        # Try to get the user's name
        user = await db.get_user(uid)
        name = f"@{user['username']}" if user and user["username"] else str(uid)
        await update.message.reply_text(
            f"✅ *{name}* (ID: `{uid}`) has been added as admin.\n\n"
            f"They can now access the Admin Control Panel.",
            parse_mode="Markdown",
        )

    elif awaiting == "remove_admin":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("⚠️ Enter a valid numeric User ID.")
            return
        if uid in ADMIN_IDS:
            await update.message.reply_text("⛔ Cannot remove Super Admins (from .env). Edit .env to remove them.")
            return
        removed = await db.remove_admin(uid)
        if removed:
            await update.message.reply_text(f"✅ Admin `{uid}` has been removed.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ User `{uid}` is not in the admin list.", parse_mode="Markdown")


# ─────────────────────────────────────────────
#  Slash Commands — Admin
# ─────────────────────────────────────────────

async def _admin_only(update: Update) -> bool:
    """Returns True if user is admin, else sends denial and returns False."""
    if await is_admin(update.effective_user.id):
        return True
    await update.message.reply_text("⛔ Access denied. Admin only.")
    return False


async def _resolve_user(query_str: str):
    """
    Resolve a user from a query string.
    Accepts: numeric ID, @username, or first name (partial match).
    Returns (user_id, user_row) or (None, None) if not found.
    """
    # 1) Numeric ID
    try:
        uid = int(query_str.lstrip("@"))
        row = await db.get_user(uid)
        return (uid, row)
    except ValueError:
        pass

    # 2) @username exact match
    row = await db.get_user_by_username(query_str)
    if row:
        return (row["user_id"], row)

    # 3) First-name partial match — only auto-resolve if exactly one hit
    matches = await db.get_users_by_name(query_str)
    if len(matches) == 1:
        return (matches[0]["user_id"], matches[0])

    return (None, None)


async def cmd_admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available admin commands."""
    await update.message.reply_text(
        "📋 *Admin Commands*\n\n"
        "📊 *Info & Stats*\n"
        "/status — Bot status & uptime info\n"
        "/rates — View all rates per category\n"
        "/drivers — List registered drivers\n"
        "/riders — List registered riders\n"
        "/users — All registered users\n"
        "/trips — Trip data & statistics\n"
        "/revenue — Revenue summary\n"
        "/groupid — Get current chat/group ID\n"
        "/whoami — Show your sender info\n"
        "/session — Current session settings\n\n"
        "💰 *Pricing*\n"
        "/setbase car 300 — Set base fare\n"
        "/setrate car 100 — Set per-km rate\n"
        "/basekm 3 — Set base free kilometers\n\n"
        "⚙️ *System*\n"
        "/setradius 10 — Set driver search radius (km)\n\n"
        "🚫 *Categories* (bike/tuk/car/minivan/van/bus)\n"
        "/blockcat bike — Disable a vehicle category\n"
        "/unblockcat bike — Enable a vehicle category\n\n"
        "👤 *Users*\n"
        "/block @username — Block a user (ID, @username, or name)\n"
        "/unblock @username — Unblock a user (ID, @username, or name)\n\n"
        "🔄 *System*\n"
        "/restart — Restart the bot session\n\n"
        "💡 Use 👑 *Admin Control ⚙️* button for a full GUI panel.",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot status."""
    if not await _admin_only(update):
        return
    drivers = await db.get_all_drivers()
    online = [d for d in drivers if d["is_online"]]
    stats = await db.get_trip_stats()
    radius = await db.get_setting("driver_radius")
    base = await db.get_setting("base_fare")
    rate = await db.get_setting("per_km_rate")
    await update.message.reply_text(
        "🤖 *TeleCabs Bot Status*\n\n"
        f"✅ Bot is *online* and running\n"
        f"🚗 Total Drivers: {len(drivers)}\n"
        f"🟢 Online Drivers: {len(online)}\n"
        f"📊 Total Trips: {stats['total']}\n"
        f"✅ Completed: {stats['completed']}\n"
        f"⏳ Pending: {stats['pending']}\n"
        f"🟢 In Progress: {stats['in_progress']}\n"
        f"📍 Driver Radius: {radius} km\n"
        f"💰 Base Fare: LKR {base}\n"
        f"📏 Per-KM Rate: LKR {rate}",
        parse_mode="Markdown",
    )


async def cmd_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all rates per category."""
    if not await _admin_only(update):
        return
    base = await db.get_setting("base_fare")
    rate = await db.get_setting("per_km_rate")
    basekm = await db.get_setting("base_km")
    waitrt = await db.get_setting("waiting_rate")
    blocked = await db.get_blocked_categories()
    blocked_str = ", ".join(blocked) if blocked else "None"
    await update.message.reply_text(
        "💰 *Current Rates*\n\n"
        f"🏁 Base Fare:         LKR {base}\n"
        f"📏 Per-KM Rate:       LKR {rate}/km\n"
        f"🛣️ Base KM (free):    {basekm} km\n"
        f"⏱ Waiting Rate:      LKR {waitrt}/min\n\n"
        f"🚫 Blocked Categories: {blocked_str}",
        parse_mode="Markdown",
    )


async def cmd_setbase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set base fare. Usage: /setbase <category> <amount>  OR  /setbase <amount>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Usage: `/setbase 300` or `/setbase car 300`", parse_mode="Markdown"
        )
        return
    # Accept both /setbase 300 and /setbase car 300 (category ignored globally for now)
    amount_str = args[-1]
    try:
        float(amount_str)
    except ValueError:
        await update.message.reply_text("⚠️ Please provide a valid number.")
        return
    await db.set_setting("base_fare", amount_str)
    await update.message.reply_text(f"✅ Base Fare updated to *LKR {amount_str}*.", parse_mode="Markdown")


async def cmd_setrate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set per-km rate. Usage: /setrate <category> <amount>  OR  /setrate <amount>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Usage: `/setrate 100` or `/setrate car 100`", parse_mode="Markdown"
        )
        return
    amount_str = args[-1]
    try:
        float(amount_str)
    except ValueError:
        await update.message.reply_text("⚠️ Please provide a valid number.")
        return
    await db.set_setting("per_km_rate", amount_str)
    await update.message.reply_text(f"✅ Per-KM Rate updated to *LKR {amount_str}*.", parse_mode="Markdown")


async def cmd_basekm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set base km. Usage: /basekm <km>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: `/basekm 3`", parse_mode="Markdown")
        return
    try:
        float(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Please provide a valid number.")
        return
    await db.set_setting("base_km", args[0])
    await update.message.reply_text(f"✅ Base KM updated to *{args[0]} km*.", parse_mode="Markdown")


async def cmd_setradius(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set driver search radius. Usage: /setradius <km>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: `/setradius 10`", parse_mode="Markdown")
        return
    try:
        float(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Please provide a valid number.")
        return
    await db.set_setting("driver_radius", args[0])
    await update.message.reply_text(f"✅ Driver Radius updated to *{args[0]} km*.", parse_mode="Markdown")


async def cmd_blockcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable a vehicle category. Usage: /blockcat <type>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Usage: `/blockcat bike`\nValid: bike, tuk, car, minivan, van, bus",
            parse_mode="Markdown",
        )
        return
    vt = args[0].lower()
    if vt not in VEHICLE_TYPES:
        await update.message.reply_text(
            "⚠️ Invalid category. Valid: bike, tuk, car, minivan, van, bus"
        )
        return
    emoji = VEHICLE_EMOJIS.get(vt, "🚗")
    await db.block_category(vt)
    await update.message.reply_text(
        f"🚫 {emoji} *{vt.title()}* has been disabled.", parse_mode="Markdown"
    )


async def cmd_unblockcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable a vehicle category. Usage: /unblockcat <type>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Usage: `/unblockcat bike`\nValid: bike, tuk, car, minivan, van, bus",
            parse_mode="Markdown",
        )
        return
    vt = args[0].lower()
    if vt not in VEHICLE_TYPES:
        await update.message.reply_text(
            "⚠️ Invalid category. Valid: bike, tuk, car, minivan, van, bus"
        )
        return
    emoji = VEHICLE_EMOJIS.get(vt, "🚗")
    await db.unblock_category(vt)
    await update.message.reply_text(
        f"✅ {emoji} *{vt.title()}* has been enabled.", parse_mode="Markdown"
    )


async def cmd_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Block a user. Usage: /block <user_id|@username|name>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Usage: `/block 123456789` or `/block @username` or `/block FirstName`",
            parse_mode="Markdown",
        )
        return
    query_str = " ".join(args)
    uid, user_row = await _resolve_user(query_str)
    if uid is None:
        await update.message.reply_text(
            f"⚠️ No user found for `{query_str}`.", parse_mode="Markdown"
        )
        return
    await db.block_user(uid, True)
    name = (
        f"@{user_row['username']}" if user_row and user_row["username"]
        else (user_row["first_name"] if user_row else str(uid))
    )
    await update.message.reply_text(
        f"⛔ *{name}* (`{uid}`) has been *blocked*.", parse_mode="Markdown"
    )


async def cmd_unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unblock a user. Usage: /unblock <user_id|@username|name>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Usage: `/unblock 123456789` or `/unblock @username` or `/unblock FirstName`",
            parse_mode="Markdown",
        )
        return
    query_str = " ".join(args)
    uid, user_row = await _resolve_user(query_str)
    if uid is None:
        await update.message.reply_text(
            f"⚠️ No user found for `{query_str}`.", parse_mode="Markdown"
        )
        return
    await db.block_user(uid, False)
    name = (
        f"@{user_row['username']}" if user_row and user_row["username"]
        else (user_row["first_name"] if user_row else str(uid))
    )
    await update.message.reply_text(
        f"✅ *{name}* (`{uid}`) has been *unblocked*.", parse_mode="Markdown"
    )


async def cmd_drivers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List registered drivers."""
    if not await _admin_only(update):
        return
    drivers = await db.get_all_drivers()
    if not drivers:
        await update.message.reply_text("No drivers registered yet.")
        return
    lines = []
    for d in drivers[:30]:
        uname = f"@{d['username']}" if d["username"] else d["first_name"]
        stars = f"{d['rating_sum']/d['rating_count']:.1f}⭐" if d["rating_count"] else "—"
        status = "🟢" if d["is_online"] else "🔴"
        lines.append(f"{status} {uname} | {d['vehicle_type']} | {d['plate_number']} | {stars}")
    await update.message.reply_text(
        f"🚖 *Registered Drivers* ({len(drivers)} total)\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


async def cmd_riders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List registered riders."""
    if not await _admin_only(update):
        return
    riders = await db.get_all_riders()
    if not riders:
        await update.message.reply_text("No riders registered yet.")
        return
    lines = [
        f"🚶 {r['username'] or r['first_name']} | ID: `{r['user_id']}` | Joined: {str(r['created_at'])[:10]}"
        for r in riders[:30]
    ]
    await update.message.reply_text(
        f"🚶 *Registered Riders* ({len(riders)} total)\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all registered users."""
    if not await _admin_only(update):
        return
    users = await db.get_all_users()
    if not users:
        await update.message.reply_text("No users registered yet.")
        return
    lines = [
        f"{'🔴' if u['is_blocked'] else '🟢'} {u['username'] or u['first_name']} | {u['role']} | `{u['user_id']}`"
        for u in users[:30]
    ]
    await update.message.reply_text(
        f"👥 *All Users* ({len(users)} total)\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


async def cmd_trips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trip statistics."""
    if not await _admin_only(update):
        return
    stats = await db.get_trip_stats()
    await update.message.reply_text(
        "📊 *Trip Statistics*\n\n"
        f"✅ Completed:   {stats['completed']}\n"
        f"❌ Cancelled:   {stats['cancelled']}\n"
        f"⏳ Pending:     {stats['pending']}\n"
        f"🟢 In Progress: {stats['in_progress']}\n"
        f"📦 Total:       {stats['total']}",
        parse_mode="Markdown",
    )


async def cmd_revenue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Revenue summary."""
    if not await _admin_only(update):
        return
    stats = await db.get_trip_stats()
    await update.message.reply_text(
        "💵 *Revenue Summary*\n\n"
        f"✅ Completed Rides: {stats['completed']}\n"
        f"💰 Total Revenue:   LKR {stats['total_revenue']:.2f}",
        parse_mode="Markdown",
    )


async def cmd_groupid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current chat/group ID."""
    if not await _admin_only(update):
        return
    chat = update.effective_chat
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 *Chat Info*\n\n"
        f"Chat ID: `{chat.id}`\n"
        f"Chat Type: {chat.type}\n"
        f"Your User ID: `{user.id}`",
        parse_mode="Markdown",
    )


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show sender info."""
    if not await _admin_only(update):
        return
    u = update.effective_user
    admin_type = "🔒 Super Admin" if is_super_admin(u.id) else "👑 Admin"
    await update.message.reply_text(
        f"🧾 *Who Am I*\n\n"
        f"Name: {u.full_name}\n"
        f"ID: `{u.id}`\n"
        f"Username: @{u.username or 'N/A'}\n"
        f"Role: {admin_type}",
        parse_mode="Markdown",
    )


async def cmd_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current session settings."""
    if not await _admin_only(update):
        return
    base = await db.get_setting("base_fare")
    rate = await db.get_setting("per_km_rate")
    basekm = await db.get_setting("base_km")
    waitrt = await db.get_setting("waiting_rate")
    radius = await db.get_setting("driver_radius")
    blocked = await db.get_blocked_categories()
    blocked_str = ", ".join(blocked) if blocked else "None"
    drivers = await db.get_all_drivers()
    online = [d for d in drivers if d["is_online"]]
    await update.message.reply_text(
        "⚙️ *Current Session Settings*\n\n"
        f"💰 Base Fare:         LKR {base}\n"
        f"📏 Per-KM Rate:       LKR {rate}/km\n"
        f"🛣️ Base KM:           {basekm} km\n"
        f"⏱ Waiting Rate:      LKR {waitrt}/min\n"
        f"📡 Driver Radius:     {radius} km\n"
        f"🚫 Blocked Cats:      {blocked_str}\n"
        f"🚗 Total Drivers:     {len(drivers)}\n"
        f"🟢 Online Drivers:    {len(online)}",
        parse_mode="Markdown",
    )


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart / reset bot session data."""
    if not await _admin_only(update):
        return
    # Clear all user_data from context (session reset)
    context.application.user_data.clear()
    context.application.chat_data.clear()
    await update.message.reply_text(
        "🔄 *Bot session has been reset!*\n\n"
        "✅ All in-memory user/chat data cleared.\n"
        "⚠️ Note: To fully restart the bot process, restart the server.",
        parse_mode="Markdown",
    )


async def cmd_resetbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hard-reset ALL stuck user sessions. Clears every user's conversation state."""
    if not await _admin_only(update):
        return

    user_count = len(context.application.user_data)
    context.application.user_data.clear()
    context.application.chat_data.clear()
    context.application.bot_data.clear()

    await update.message.reply_text(
        f"🔄 *Full Bot Reset Complete!*\n\n"
        f"✅ Cleared {user_count} user session(s).\n"
        f"✅ All stuck conversations have been reset.\n\n"
        f"All users can now use /start to return to the main menu.",
        parse_mode="Markdown",
    )


async def cmd_apistatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Live-test all external APIs and report their status."""
    if not await _admin_only(update):
        return

    from config import GOOGLE_MAPS_API_KEY
    import aiohttp

    await update.message.reply_text("🔍 Testing all APIs... please wait.")

    lines = ["🔌 *API Status Check*\n"]

    # Shared test coordinates — Colombo → Kandy
    lat1, lon1 = 6.9271, 79.8612
    lat2, lon2 = 7.2906, 80.6337

    # ── 1. Google Distance Matrix ────────────────────────────────────────────
    if GOOGLE_MAPS_API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://maps.googleapis.com/maps/api/distancematrix/json",
                    params={
                        "origins":      f"{lat1},{lon1}",
                        "destinations": f"{lat2},{lon2}",
                        "mode":   "driving",
                        "key":    GOOGLE_MAPS_API_KEY,
                    },
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    d = await resp.json(content_type=None)
            s = d.get("status", "?")
            if s == "OK":
                km = d["rows"][0]["elements"][0]["distance"]["value"] / 1000
                lines.append(f"✅ *Google Distance Matrix* — {km:.1f} km (Colombo→Kandy)")
            else:
                lines.append(f"❌ *Google Distance Matrix* — {s}")
        except Exception as e:
            lines.append(f"❌ *Google Distance Matrix* — Error: {e}")

        # ── 2. Google Geocoding ──────────────────────────────────────────────
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={"latlng": f"{lat1},{lon1}", "key": GOOGLE_MAPS_API_KEY},
                    timeout=aiohttp.ClientTimeout(total=6),
                ) as resp:
                    d = await resp.json(content_type=None)
            s = d.get("status", "?")
            if s == "OK":
                lines.append(f"✅ *Google Geocoding API* — working")
            else:
                lines.append(f"❌ *Google Geocoding API* — {s}\n   ⚠️ Enable 'Geocoding API' in Google Cloud Console")
        except Exception as e:
            lines.append(f"❌ *Google Geocoding API* — Error: {e}")

        # ── 3. Google Places ─────────────────────────────────────────────────
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://maps.googleapis.com/maps/api/place/textsearch/json",
                    params={"query": "Kandy Sri Lanka", "key": GOOGLE_MAPS_API_KEY},
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    d = await resp.json(content_type=None)
            s = d.get("status", "?")
            if s == "OK":
                lines.append(f"✅ *Google Places API* — working (best location search)")
            else:
                lines.append(f"❌ *Google Places API* — {s}\n   ⚠️ Enable 'Places API' in Google Cloud Console")
        except Exception as e:
            lines.append(f"❌ *Google Places API* — Error: {e}")
    else:
        lines.append("⚠️ *Google APIs* — No API key set in .env")

    # ── 4. OSRM ─────────────────────────────────────────────────────────────
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://router.project-osrm.org/route/v1/driving/"
                f"{lon1},{lat1};{lon2},{lat2}?overview=false",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                d = await resp.json(content_type=None)
        if d.get("code") == "Ok":
            km = d["routes"][0]["distance"] / 1000
            lines.append(f"✅ *OSRM* — {km:.1f} km (Colombo→Kandy)")
        else:
            lines.append(f"❌ *OSRM* — {d.get('code', 'Error')}")
    except Exception as e:
        lines.append(f"❌ *OSRM* — Error: {e}")

    # ── 5. Nominatim ────────────────────────────────────────────────────────
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat1, "lon": lon1, "format": "json"},
                headers={"User-Agent": "TeleCabsBot/2.0"},
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                d = await resp.json(content_type=None)
        if "address" in d:
            lines.append(f"✅ *Nominatim* — working (free reverse geocoding)")
        else:
            lines.append(f"❌ *Nominatim* — unexpected response")
    except Exception as e:
        lines.append(f"❌ *Nominatim* — Error: {e}")

    # ── 6. Photon ───────────────────────────────────────────────────────────
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://photon.komoot.io/api/",
                params={"q": "Kandy", "limit": 1, "lang": "en"},
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                d = await resp.json(content_type=None)
        if d.get("features"):
            lines.append(f"✅ *Photon* — working (free location search)")
        else:
            lines.append(f"⚠️ *Photon* — no results")
    except Exception as e:
        lines.append(f"❌ *Photon* — Error: {e}")

    lines.append("\n💡 *Tips to improve accuracy:*")
    lines.append("• Enable *Geocoding API* → better reverse geocoding")
    lines.append("• Enable *Places API* → find hotels, roads, local names")
    lines.append("Both are free tier eligible at console.cloud.google.com")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )

