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
    global_base = float(await db.get_setting("base_fare")   or 100)
    global_rate = float(await db.get_setting("per_km_rate") or 50)

    rows = []
    for vt in VEHICLE_TYPES:
        emoji  = VEHICLE_EMOJIS.get(vt, "🚗")
        b_raw  = await db.get_setting(f"base_fare_{vt}")
        r_raw  = await db.get_setting(f"per_km_rate_{vt}")
        b_val  = float(b_raw) if b_raw else global_base
        r_val  = float(r_raw) if r_raw else global_rate
        custom = "✅" if (b_raw or r_raw) else "🔗"
        label  = f"{custom} {emoji} {vt.title()} — LKR {b_val} + {r_val}/km"
        rows.append([InlineKeyboardButton(label, callback_data=f"adm_veh_{vt}")])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="adm_back")])
    return InlineKeyboardMarkup(rows)


def vehicle_edit_keyboard(vt: str) -> InlineKeyboardMarkup:
    """Edit keyboard for a specific vehicle type."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Set Base Fare",    callback_data=f"adm_setvbase_{vt}")],
        [InlineKeyboardButton("📏 Set Per-KM Rate",  callback_data=f"adm_setvrate_{vt}")],
        [InlineKeyboardButton("🔄 Reset to Global",   callback_data=f"adm_resetveh_{vt}")],
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
            and not data.startswith("adm_setvrate_") and not data.startswith("adm_resetveh_"):
        vt = data.replace("adm_veh_", "").lower()
        if vt not in VEHICLE_TYPES:
            await query.answer("⚠️ Unknown vehicle type.", show_alert=True)
            return
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        global_base = float(await db.get_setting("base_fare")   or 100)
        global_rate = float(await db.get_setting("per_km_rate") or 50)
        b_raw = await db.get_setting(f"base_fare_{vt}")
        r_raw = await db.get_setting(f"per_km_rate_{vt}")
        b_val = float(b_raw) if b_raw else global_base
        r_val = float(r_raw) if r_raw else global_rate
        status = "✅ Custom set" if (b_raw or r_raw) else "🔗 Using global"
        await query.edit_message_text(
            f"{emoji} *{vt.title()} Pricing*\n\n"
            f"Status: {status}\n\n"
            f"💰 Base Fare:    LKR {b_val}\n"
            f"📏 Per-KM Rate:  LKR {r_val}/km\n\n"
            f"*(Global: LKR {global_base} base + LKR {global_rate}/km)*\n\n"
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

    elif data.startswith("adm_resetveh_"):
        vt = data.replace("adm_resetveh_", "").lower()
        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        # Delete custom rates → fall back to global
        await db.set_setting(f"base_fare_{vt}",   "")
        await db.set_setting(f"per_km_rate_{vt}", "")
        await query.edit_message_text(
            f"✅ {emoji} *{vt.title()}* rates reset to global defaults.",
            parse_mode="Markdown",
            reply_markup=await vehicle_pricing_keyboard(),
        )


    elif data == "adm_distance":
        current = (await db.get_setting("distance_method") or "osrm").lower()
        label   = METHOD_LABELS.get(current, current)
        desc    = METHOD_DESCRIPTIONS.get(current, "")
        google_key = "✅ Set" if __import__('config').GOOGLE_MAPS_API_KEY else "❌ Not set"
        await query.edit_message_text(
            f"🗺️ *Distance Calculation Method*\n\n"
            f"*Active:* {label}\n"
            f"📝 {desc}\n\n"
            f"🔑 Google API Key: {google_key}\n\n"
            f"Tap a method below to switch:",
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
        label = METHOD_LABELS.get(method, method)
        desc  = METHOD_DESCRIPTIONS.get(method, "")
        await query.edit_message_text(
            f"✅ *Distance method switched!*\n\n"
            f"*New method:* {label}\n"
            f"📝 {desc}\n\n"
            f"All new fare estimates will use this method.",
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
            "🚫 Enter vehicle type to *disable* (car / tuk / bike / van):",
            parse_mode="Markdown",
        )

    elif data == "adm_unblockcat":
        context.user_data["adm_awaiting"] = "unblock_cat"
        await query.edit_message_text(
            "✅ Enter vehicle type to *enable* (car / tuk / bike / van):",
            parse_mode="Markdown",
        )

    elif data == "adm_blockuser":
        context.user_data["adm_awaiting"] = "block_user"
        await query.edit_message_text("⛔ Enter the *User ID* to block:", parse_mode="Markdown")

    elif data == "adm_unblockuser":
        context.user_data["adm_awaiting"] = "unblock_user"
        await query.edit_message_text("✅ Enter the *User ID* to unblock:", parse_mode="Markdown")


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

    elif awaiting.startswith("vbase_") or awaiting.startswith("vrate_"):
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
        else:
            vt  = awaiting.replace("vrate_", "")
            key = f"per_km_rate_{vt}"
            lbl = "Per-KM Rate"

        emoji = VEHICLE_EMOJIS.get(vt, "🚗")
        await db.set_setting(key, text)
        await update.message.reply_text(
            f"✅ {emoji} *{vt.title()} — {lbl}* set to `LKR {text}`.",
            parse_mode="Markdown",
        )


    elif awaiting == "block_cat":
        vt = text.lower()
        if vt not in ("car", "tuk", "bike", "van"):
            await update.message.reply_text("⚠️ Invalid category. Use: car, tuk, bike, van")
            return
        await db.block_category(vt)
        await update.message.reply_text(f"🚫 Category *{vt}* disabled.", parse_mode="Markdown")

    elif awaiting == "unblock_cat":
        vt = text.lower()
        await db.unblock_category(vt)
        await update.message.reply_text(f"✅ Category *{vt}* enabled.", parse_mode="Markdown")

    elif awaiting == "block_user":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("⚠️ Enter a valid numeric User ID.")
            return
        await db.block_user(uid, True)
        await update.message.reply_text(f"⛔ User `{uid}` has been blocked.", parse_mode="Markdown")

    elif awaiting == "unblock_user":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("⚠️ Enter a valid numeric User ID.")
            return
        await db.block_user(uid, False)
        await update.message.reply_text(f"✅ User `{uid}` has been unblocked.", parse_mode="Markdown")

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
        "🚫 *Categories*\n"
        "/blockcat bike — Disable a vehicle category\n"
        "/unblockcat bike — Enable a vehicle category\n\n"
        "👤 *Users*\n"
        "/block 123456 — Block a user by ID\n"
        "/unblock 123456 — Unblock a user by ID\n\n"
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
    """Disable a vehicle category. Usage: /blockcat bike"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: `/blockcat bike`\nValid: car, tuk, bike, van", parse_mode="Markdown")
        return
    vt = args[0].lower()
    if vt not in ("car", "tuk", "bike", "van"):
        await update.message.reply_text("⚠️ Invalid category. Use: car, tuk, bike, van")
        return
    await db.block_category(vt)
    await update.message.reply_text(f"🚫 Category *{vt}* has been disabled.", parse_mode="Markdown")


async def cmd_unblockcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable a vehicle category. Usage: /unblockcat bike"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: `/unblockcat bike`", parse_mode="Markdown")
        return
    vt = args[0].lower()
    await db.unblock_category(vt)
    await update.message.reply_text(f"✅ Category *{vt}* has been enabled.", parse_mode="Markdown")


async def cmd_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Block a user. Usage: /block <user_id>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: `/block 123456789`", parse_mode="Markdown")
        return
    try:
        uid = int(args[0].lstrip("@"))
    except ValueError:
        await update.message.reply_text("⚠️ Please provide a valid numeric User ID.")
        return
    await db.block_user(uid, True)
    await update.message.reply_text(f"⛔ User `{uid}` has been *blocked*.", parse_mode="Markdown")


async def cmd_unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unblock a user. Usage: /unblock <user_id>"""
    if not await _admin_only(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: `/unblock 123456789`", parse_mode="Markdown")
        return
    try:
        uid = int(args[0].lstrip("@"))
    except ValueError:
        await update.message.reply_text("⚠️ Please provide a valid numeric User ID.")
        return
    await db.block_user(uid, False)
    await update.message.reply_text(f"✅ User `{uid}` has been *unblocked*.", parse_mode="Markdown")


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
