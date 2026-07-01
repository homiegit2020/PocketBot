"""
main.py
=======
Bot entry point:
  - Pyrogram Client setup
  - All handlers registered
  - APScheduler for session refresh
  - aiohttp health-check web server on port 8080
  - Auto-restart loop
"""

import asyncio
import os
import time
from datetime import datetime

from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

load_dotenv()

BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "pocket_bot_session")

_START_TIME = time.time()

# ── Database ──────────────────────────────────────────────────────────────────
from database.db import init_db
import database.db as db_module

# ── Handlers ──────────────────────────────────────────────────────────────────
from handlers.start    import (cmd_start, cb_has_account, cb_new_account,
                                handle_text_input, get_state)
from handlers.account  import cmd_account, cb_account
from handlers.settings import (cmd_settings, cb_settings, cb_set_amount,
                                cb_set_time, cb_set_martin, cb_set_mode,
                                cb_mode_demo, cb_mode_real)
from handlers.trading  import (cb_start_trade, cb_start_session, cb_start_session_n,
                                cb_execute_session, cb_deposited, cb_main_menu,
                                cb_support)
from handlers.admin    import (cmd_admin, cb_admin, cb_adm_users, cb_adm_banned,
                                cb_adm_stats, cb_adm_balances, cb_adm_broadcast,
                                cb_adm_search, cb_adm_ban, cb_adm_unban,
                                cb_adm_msg, cb_adm_botsettings, cb_adm_actlog,
                                cb_adm_export)

# ── Services ──────────────────────────────────────────────────────────────────
from services.session_manager import refresh_all_sessions
from utils.logger import log, log_error


# ── Pyrogram client ───────────────────────────────────────────────────────────

app = Client(
    name=SESSION_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)


# ── Register handlers ─────────────────────────────────────────────────────────

@app.on_message(filters.command("start") & filters.private)
async def _start(client, message): await cmd_start(client, message)

@app.on_message(filters.command("account") & filters.private)
async def _account(client, message): await cmd_account(client, message)

@app.on_message(filters.command("settings") & filters.private)
async def _settings(client, message): await cmd_settings(client, message)

@app.on_message(filters.command("admin") & filters.private)
async def _admin(client, message): await cmd_admin(client, message)


@app.on_message(filters.text & filters.private & ~filters.command(["start","account","settings","admin"]))
async def _text(client, message):
    uid = message.from_user.id
    if get_state(uid) is not None:
        await handle_text_input(client, message)


# ── Callback query router ─────────────────────────────────────────────────────

_CB_MAP = {
    "has_account":     cb_has_account,
    "new_account":     cb_new_account,
    "start_trade":     cb_start_trade,
    "start_session":   cb_start_session,
    "execute_session": cb_execute_session,
    "deposited":       cb_deposited,
    "main_menu":       cb_main_menu,
    "support":         cb_support,
    "account":         cb_account,
    "settings":        cb_settings,
    "set_amount":      cb_set_amount,
    "set_time":        cb_set_time,
    "set_martin":      cb_set_martin,
    "set_mode":        cb_set_mode,
    "mode_demo":       cb_mode_demo,
    "mode_real":       cb_mode_real,
    "admin":           cb_admin,
    "adm_banned":      cb_adm_banned,
    "adm_stats":       cb_adm_stats,
    "adm_balances":    cb_adm_balances,
    "adm_broadcast":   cb_adm_broadcast,
    "adm_search":      cb_adm_search,
    "adm_botsettings": cb_adm_botsettings,
    "adm_actlog":      cb_adm_actlog,
    "adm_export":      cb_adm_export,
}


@app.on_callback_query()
async def _callback_router(client: Client, query: CallbackQuery):
    data = query.data or ""
    try:
        # Exact match
        if data in _CB_MAP:
            await _CB_MAP[data](client, query)
            return

        # Prefix match
        if data.startswith("adm_users_"):
            await cb_adm_users(client, query)
        elif data.startswith("adm_ban_"):
            await cb_adm_ban(client, query)
        elif data.startswith("adm_unban_"):
            await cb_adm_unban(client, query)
        elif data.startswith("adm_msg_"):
            await cb_adm_msg(client, query)
        elif data.startswith("start_session_"):
            await cb_start_session_n(client, query)
        else:
            await query.answer()

    except Exception as e:
        log_error(f"Callback error [{data}]: {e}", exc_info=True)
        try:
            await query.answer("⚠️ An error occurred. Please try again.", show_alert=True)
        except Exception:
            pass


# ── Health-check web server ───────────────────────────────────────────────────

async def _health(request: web.Request) -> web.Response:
    uptime = int(time.time() - _START_TIME)
    total_users = await db_module.count_users()
    return web.json_response({
        "status": "running",
        "uptime_seconds": uptime,
        "users": total_users,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def start_webserver(port: int = 8080) -> None:
    web_app = web.Application()
    web_app.router.add_get("/", _health)
    web_app.router.add_get("/health", _health)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log(f"✅ Web server running on port {port}")


# ── Scheduler ────────────────────────────────────────────────────────────────

scheduler = AsyncIOScheduler()


def _setup_scheduler():
    scheduler.add_job(
        refresh_all_sessions,
        trigger="interval",
        hours=6,
        id="refresh_sessions",
        replace_existing=True,
    )
    scheduler.start()
    log("✅ Scheduler started")


# ── Main loop with auto-restart ───────────────────────────────────────────────

async def main():
    await init_db()
    _setup_scheduler()
    await start_webserver()

    await app.start()
    me = await app.get_me()
    log(f"✅ Bot connected to Telegram: @{me.username}")
    log("✅ Bot is ready")

    # Proper Pyrogram idle — keeps bot alive and processing updates
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
