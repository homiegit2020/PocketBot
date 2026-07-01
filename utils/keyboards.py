from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ── Start / Welcome ──────────────────────────────────────────────────────────

def kb_welcome() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Official Guide", url="https://pocketoption.com"),
            InlineKeyboardButton("🎧 Support", callback_data="support"),
        ]
    ])


def kb_has_account() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, I already have one", callback_data="has_account")],
        [InlineKeyboardButton("🆕 No, create a new one", callback_data="new_account")],
    ])


# ── After account linked ──────────────────────────────────────────────────────

def kb_start_trade() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start Trade", callback_data="start_trade")],
    ])


def kb_start_session() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start Session", callback_data="start_session")],
    ])


def kb_execute_session() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Execute Session", callback_data="execute_session")],
    ])


def kb_session_complete(session_num: int, total_sessions: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💰 Make a Deposit", url="https://pocketoption.com/en/cabinet/balance/")],
        [InlineKeyboardButton("✅ I deposited", callback_data="deposited")],
    ]
    if session_num < total_sessions:
        rows.append([InlineKeyboardButton(f"▶️ Start Session {session_num + 1}/{total_sessions}", callback_data=f"start_session_{session_num + 1}")])
    rows += [
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"), InlineKeyboardButton("🎧 Support", callback_data="support")],
        [InlineKeyboardButton("📖 Official Guide", url="https://pocketoption.com")],
    ]
    return InlineKeyboardMarkup(rows)


# ── Settings ──────────────────────────────────────────────────────────────────

def kb_settings() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 Trade Amount", callback_data="set_amount"), InlineKeyboardButton("⏱️ Trade Time", callback_data="set_time")],
        [InlineKeyboardButton("📊 Martingale Steps", callback_data="set_martin"), InlineKeyboardButton("🔄 Mode", callback_data="set_mode")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
    ])


def kb_mode_select() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Demo", callback_data="mode_demo"), InlineKeyboardButton("🔴 Real", callback_data="mode_real")],
        [InlineKeyboardButton("◀️ Back", callback_data="settings")],
    ])


# ── Account ───────────────────────────────────────────────────────────────────

def kb_account() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings"), InlineKeyboardButton("▶️ Start Trade", callback_data="start_trade")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
    ])


# ── Admin ─────────────────────────────────────────────────────────────────────

def kb_admin_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 All Users", callback_data="adm_users_0"), InlineKeyboardButton("🚫 Banned Users", callback_data="adm_banned")],
        [InlineKeyboardButton("📊 Trade Stats", callback_data="adm_stats"), InlineKeyboardButton("💰 Balances", callback_data="adm_balances")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"), InlineKeyboardButton("🔍 Search User", callback_data="adm_search")],
        [InlineKeyboardButton("⚙️ Bot Settings", callback_data="adm_botsettings"), InlineKeyboardButton("📋 Activity Log", callback_data="adm_actlog")],
        [InlineKeyboardButton("📁 Export CSV", callback_data="adm_export")],
    ])


def kb_admin_user(telegram_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    ban_btn = InlineKeyboardButton("✅ Unban", callback_data=f"adm_unban_{telegram_id}") if is_banned else InlineKeyboardButton("🚫 Ban", callback_data=f"adm_ban_{telegram_id}")
    return InlineKeyboardMarkup([
        [ban_btn, InlineKeyboardButton("✉️ Message", callback_data=f"adm_msg_{telegram_id}")],
        [InlineKeyboardButton("◀️ Back to List", callback_data="adm_users_0")],
    ])


def kb_admin_users_page(page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"adm_users_{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️ Next", callback_data=f"adm_users_{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("◀️ Admin Menu", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start Trade", callback_data="start_trade"), InlineKeyboardButton("👤 Account", callback_data="account")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings"), InlineKeyboardButton("🎧 Support", callback_data="support")],
    ])
