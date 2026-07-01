"""
handlers/admin.py
=================
Full admin panel — only accessible to ADMIN_ID from .env
"""

import csv
import io
import os
from datetime import datetime

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery, InputMediaDocument

from database import db
from utils import keyboards as kb
from utils.logger import log, log_error

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
START_TIME = datetime.utcnow()

PER_PAGE = 10


def _is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def _format_user_detail(user: dict) -> str:
    mode = "🟢 Demo" if user.get("mode") == "demo" else "🔴 Real"
    banned = "🚫 BANNED" if user.get("is_banned") else "✅ Active"
    return (
        f"👤 <b>User #{user['telegram_id']}</b>\n\n"
        f"Email: <code>{user.get('email', 'N/A')}</code>\n"
        f"Account ID: <code>{user.get('account_id', 'N/A')}</code>\n"
        f"Mode: {mode} | Status: {banned}\n\n"
        f"💰 Real: ${user.get('real_balance', 0):,.2f}\n"
        f"🎮 Demo: ${user.get('demo_balance', 0):,.2f}\n\n"
        f"Trade Amount: ${user.get('trade_amount', 1):.2f}\n"
        f"Trade Time: {user.get('trade_time', 60)}s\n"
        f"Sessions: {user.get('sessions_completed', 0)}\n\n"
        f"Created: {user.get('created_at', 'N/A')}\n"
        f"Last Active: {user.get('last_active', 'N/A')}\n"
        + (f"\nBan Reason: {user['ban_reason']}" if user.get('ban_reason') else "")
    )


# ── /admin command ────────────────────────────────────────────────────────────

async def cmd_admin(client: Client, message: Message):
    uid = message.from_user.id
    if not _is_admin(uid):
        await message.reply("⛔ Access denied.")
        return

    uptime_sec = int((datetime.utcnow() - START_TIME).total_seconds())
    uptime_str = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m"

    total_users  = await db.count_users()
    active_today = await db.count_active_today()
    banned       = await db.count_banned_users()
    total_trades = await db.count_total_trades()

    text = (
        "👑 <b>ADMIN PANEL</b>\n\n"
        "📊 System Stats:\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Active Today: {active_today}\n"
        f"🚫 Banned: {banned}\n"
        f"📈 Total Trades: {total_trades}\n"
        f"🕐 Bot Uptime: {uptime_str}\n"
        "🟢 Status: Online"
    )
    await message.reply(text, reply_markup=kb.kb_admin_main())


async def cb_admin(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    if not _is_admin(uid):
        await query.answer("⛔ Access denied", show_alert=True)
        return

    uptime_sec = int((datetime.utcnow() - START_TIME).total_seconds())
    uptime_str = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m"
    total_users  = await db.count_users()
    active_today = await db.count_active_today()
    banned       = await db.count_banned_users()
    total_trades = await db.count_total_trades()

    text = (
        "👑 <b>ADMIN PANEL</b>\n\n"
        "📊 System Stats:\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Active Today: {active_today}\n"
        f"🚫 Banned: {banned}\n"
        f"📈 Total Trades: {total_trades}\n"
        f"🕐 Bot Uptime: {uptime_str}\n"
        "🟢 Status: Online"
    )
    await query.answer()
    await query.message.edit_text(text, reply_markup=kb.kb_admin_main())


# ── All Users list ────────────────────────────────────────────────────────────

async def cb_adm_users(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    if not _is_admin(uid):
        await query.answer("⛔", show_alert=True)
        return

    page = int(query.data.split("_")[-1])
    total = await db.count_users()
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    users = await db.get_users_page(page, PER_PAGE)

    lines = [f"👥 <b>All Users — Page {page + 1}/{total_pages}</b>\n"]
    for u in users:
        status = "🚫" if u["is_banned"] else "✅"
        lines.append(
            f"{status} <code>{u['telegram_id']}</code> | "
            f"{u.get('email','N/A')[:20]} | "
            f"${u.get('demo_balance',0):,.0f}"
        )
        lines.append(f"  └ Sessions: {u.get('sessions_completed',0)} | Mode: {u.get('mode','demo')}")

    await query.answer()
    await query.message.edit_text(
        "\n".join(lines),
        reply_markup=kb.kb_admin_users_page(page, total_pages),
    )


# ── Banned users ──────────────────────────────────────────────────────────────

async def cb_adm_banned(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    users = await db.get_all_users()
    banned_users = [u for u in users if u.get("is_banned")]
    if not banned_users:
        await query.answer("No banned users", show_alert=True)
        return

    lines = ["🚫 <b>Banned Users</b>\n"]
    for u in banned_users[:30]:
        lines.append(
            f"• <code>{u['telegram_id']}</code> {u.get('email','N/A')} "
            f"— {u.get('ban_reason','')}"
        )

    await query.answer()
    await query.message.edit_text(
        "\n".join(lines),
        reply_markup=kb.kb_admin_main(),
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

async def cb_adm_stats(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    total_trades = await db.count_total_trades()
    total_users  = await db.count_users()

    await query.answer()
    await query.message.edit_text(
        f"📊 <b>Trade Stats</b>\n\n"
        f"Total Users: {total_users}\n"
        f"Total Trades: {total_trades}",
        reply_markup=kb.kb_admin_main(),
    )


# ── Balances ──────────────────────────────────────────────────────────────────

async def cb_adm_balances(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    users = await db.get_all_users()
    lines = ["💰 <b>Balances (top 20 by demo)</b>\n"]
    sorted_users = sorted(users, key=lambda u: u.get("demo_balance", 0), reverse=True)[:20]
    for u in sorted_users:
        lines.append(
            f"<code>{u['telegram_id']}</code> | "
            f"Demo: ${u.get('demo_balance',0):,.2f} | "
            f"Real: ${u.get('real_balance',0):,.2f}"
        )

    await query.answer()
    await query.message.edit_text("\n".join(lines), reply_markup=kb.kb_admin_main())


# ── Broadcast ─────────────────────────────────────────────────────────────────

async def cb_adm_broadcast(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    from handlers.start import _set_state
    _set_state(query.from_user.id, "await_broadcast_msg")
    await query.answer()
    await query.message.reply("📢 Enter the broadcast message to send to ALL users:")


# ── Search ────────────────────────────────────────────────────────────────────

async def cb_adm_search(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    from handlers.start import _set_state
    _set_state(query.from_user.id, "await_search")
    await query.answer()
    await query.message.reply("🔍 Enter Telegram ID or email to search:")


# ── Ban / Unban ───────────────────────────────────────────────────────────────

async def cb_adm_ban(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    target_id = int(query.data.split("_")[-1])
    await db.ban_user(target_id, reason="Banned by admin")
    await query.answer(f"✅ User {target_id} banned")

    user = await db.get_user(target_id)
    if user:
        await query.message.edit_text(
            _format_user_detail(user),
            reply_markup=kb.kb_admin_user(target_id, True),
        )


async def cb_adm_unban(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    target_id = int(query.data.split("_")[-1])
    await db.unban_user(target_id)
    await query.answer(f"✅ User {target_id} unbanned")

    user = await db.get_user(target_id)
    if user:
        await query.message.edit_text(
            _format_user_detail(user),
            reply_markup=kb.kb_admin_user(target_id, False),
        )


# ── Message user ──────────────────────────────────────────────────────────────

async def cb_adm_msg(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    target_id = int(query.data.split("_")[-1])
    from handlers.start import _set_state
    _set_state(query.from_user.id, f"await_admin_msg_{target_id}")
    await query.answer()
    await query.message.reply(f"✉️ Enter message for user <code>{target_id}</code>:")


# ── Bot Settings ──────────────────────────────────────────────────────────────

async def cb_adm_botsettings(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    max_sessions  = await db.get_setting("max_sessions", "3")
    default_amount = await db.get_setting("default_amount", "1.0")
    maintenance   = await db.get_setting("maintenance", "off")

    await query.answer()
    await query.message.edit_text(
        f"⚙️ <b>Bot Settings</b>\n\n"
        f"Max Sessions Per User: {max_sessions}\n"
        f"Default Trade Amount: ${default_amount}\n"
        f"Maintenance Mode: {maintenance}\n\n"
        "Use /set_max_sessions N, /set_default_amount N, /maintenance on|off",
        reply_markup=kb.kb_admin_main(),
    )


# ── Activity log ──────────────────────────────────────────────────────────────

async def cb_adm_actlog(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    logs = await db.get_activity_log(limit=20)
    lines = ["📋 <b>Activity Log (last 20)</b>\n"]
    for entry in logs:
        lines.append(
            f"[{entry['timestamp'][:16]}] <code>{entry['telegram_id']}</code> "
            f"• {entry['event_type']} — {(entry['details'] or '')[:40]}"
        )

    await query.answer()
    await query.message.edit_text("\n".join(lines), reply_markup=kb.kb_admin_main())


# ── Export CSV ────────────────────────────────────────────────────────────────

async def cb_adm_export(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user.id):
        await query.answer("⛔", show_alert=True)
        return

    await query.answer("⏳ Generating CSV...")

    # Users CSV
    users = await db.get_all_users()
    users_buf = io.StringIO()
    if users:
        writer = csv.DictWriter(users_buf, fieldnames=list(users[0].keys()))
        writer.writeheader()
        for u in users:
            # Don't export passwords in CSV
            u_safe = {**u, "password": "***", "ssid": "***", "po_session": "***"}
            writer.writerow(u_safe)

    users_bytes = io.BytesIO(users_buf.getvalue().encode())
    users_bytes.name = "users.csv"

    # Trades CSV
    all_trades = []
    for u in users[:200]:  # limit to avoid huge files
        trades = await db.get_user_trades(u["telegram_id"])
        all_trades.extend(trades)

    trades_buf = io.StringIO()
    if all_trades:
        writer = csv.DictWriter(trades_buf, fieldnames=list(all_trades[0].keys()))
        writer.writeheader()
        writer.writerows(all_trades)

    trades_bytes = io.BytesIO(trades_buf.getvalue().encode())
    trades_bytes.name = "trades.csv"

    try:
        await client.send_document(query.from_user.id, users_bytes, file_name="users.csv", caption="👥 Users export")
        await client.send_document(query.from_user.id, trades_bytes, file_name="trades.csv", caption="📈 Trades export")
    except Exception as e:
        await query.message.reply(f"❌ Export failed: {e}")
