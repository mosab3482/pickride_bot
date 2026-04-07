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
        [InlineKeyboardButton("📍 System Settings",         callback_data="adm_system")],
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
        [InlineKeyboardButton("⬅️ Back",              callback_data="adm_back")],
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
