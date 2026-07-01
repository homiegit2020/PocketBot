"""
handlers/trading.py
===================
Trade session flow:
  start_trade → session intro → scan → signal → execute_session → live trade updates
"""

import asyncio
from typing import Optional

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery

from database import db
from services import signals as sig_svc
from services import trading_engine as eng
from services.session_manager import ensure_fresh_session
from utils import keyboards as kb
from utils import messages as msg
from utils.logger import log, log_error

TOTAL_SESSIONS = 3
TRADES_PER_SESSION = 10

# Active session tracking per user
_active_sessions: dict[int, bool] = {}


# ── Start Trade ───────────────────────────────────────────────────────────────

async def cb_start_trade(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    user = await db.get_user(uid)

    if not user:
        await query.answer("Please /start first", show_alert=True)
        return
    if user.get("is_banned"):
        await query.answer("🚫 Banned", show_alert=True)
        return
    if not user.get("ssid"):
        await query.answer("⚠️ No session found. Please log in again.", show_alert=True)
        return

    sessions_done = user.get("sessions_completed", 0)
    next_session = sessions_done + 1

    if next_session > TOTAL_SESSIONS:
        await query.answer()
        await query.message.reply(
            "✅ All 3 sessions completed!\n\nMake a deposit to continue trading with real funds.",
            reply_markup=kb.kb_session_complete(TOTAL_SESSIONS, TOTAL_SESSIONS),
        )
        return

    await query.answer()
    await query.message.reply(
        msg.msg_session_intro(next_session, TOTAL_SESSIONS, TRADES_PER_SESSION),
        reply_markup=kb.kb_start_session(),
    )


async def cb_start_session_n(client: Client, query: CallbackQuery):
    """Handles start_session_N callbacks for subsequent sessions."""
    data = query.data  # e.g. "start_session_2"
    try:
        n = int(data.split("_")[-1])
    except Exception:
        n = 1
    uid = query.from_user.id
    user = await db.get_user(uid)

    if not user or not user.get("ssid"):
        await query.answer("⚠️ No session. Please /start again.", show_alert=True)
        return

    await query.answer()
    await query.message.reply(
        msg.msg_session_intro(n, TOTAL_SESSIONS, TRADES_PER_SESSION),
        reply_markup=kb.kb_start_session(),
    )


async def cb_start_session(client: Client, query: CallbackQuery):
    """Start session = run market scan then show signal."""
    uid = query.from_user.id

    if _active_sessions.get(uid):
        await query.answer("⏳ Session already running", show_alert=True)
        return

    user = await db.get_user(uid)
    if not user or not user.get("ssid"):
        await query.answer("⚠️ No session. Please /start again.", show_alert=True)
        return

    # Ensure session is fresh
    ok = await ensure_fresh_session(uid)
    if not ok:
        await query.answer("⚠️ Session expired. Please /start again.", show_alert=True)
        return

    await query.answer()
    _active_sessions[uid] = True

    try:
        await _run_scan_and_signal(client, query, user)
    except Exception as e:
        log_error(f"cb_start_session error for {uid}: {e}", exc_info=True)
        _active_sessions.pop(uid, None)
        await query.message.reply(msg.msg_error(f"Session error: {e}"))


async def _run_scan_and_signal(client: Client, query: CallbackQuery, user: dict):
    uid = user["telegram_id"]

    # ── Market scan animation ──────────────────────────────────────────────
    scan_msg = await query.message.reply("⚙️ <b>System Status: Scanning Market...</b>")

    completed_steps = []
    for step in msg.SCAN_STEPS:
        await asyncio.sleep(1)
        completed_steps.append(step)
        await scan_msg.edit_text(msg.msg_scan_step(completed_steps))

    await asyncio.sleep(0.5)

    # ── Connect to Pocket Option ───────────────────────────────────────────
    user = await db.get_user(uid)  # refresh
    ssid = user.get("ssid", "")

    conn = await eng.get_connection(uid, ssid)
    if conn is None:
        _active_sessions.pop(uid, None)
        await scan_msg.edit_text(
            "⚠️ Could not connect to Pocket Option.\n"
            "Session may be expired. Please /start again."
        )
        return

    # ── Generate signal ────────────────────────────────────────────────────
    signal = await sig_svc.generate_signal(conn.api if conn.api else _DummyApi())

    # ── Show signal and pin ────────────────────────────────────────────────
    signal_text = msg.msg_signal(signal["direction"], signal["display_name"], signal["payout"])
    signal_msg = await query.message.reply(signal_text, reply_markup=kb.kb_execute_session())

    try:
        await client.pin_chat_message(uid, signal_msg.id, both_sides=False, disable_notification=True)
    except Exception:
        pass  # Pinning fails in groups/channels — ignore

    _active_sessions.pop(uid, None)


async def cb_execute_session(client: Client, query: CallbackQuery):
    """Execute all 10 trades sequentially."""
    uid = query.from_user.id

    if _active_sessions.get(uid):
        await query.answer("⏳ Already executing", show_alert=True)
        return

    user = await db.get_user(uid)
    if not user or not user.get("ssid"):
        await query.answer("⚠️ No session. Please /start again.", show_alert=True)
        return

    # Parse signal from the message text
    signal = _parse_signal_from_message(query.message.text or "")

    await query.answer()
    _active_sessions[uid] = True
    # Edit execute button away
    await query.message.edit_reply_markup(reply_markup=None)

    try:
        await _run_all_trades(client, query, user, signal)
    except Exception as e:
        log_error(f"cb_execute_session error for {uid}: {e}", exc_info=True)
        await query.message.reply(msg.msg_error(f"Trade execution error: {e}"))
    finally:
        _active_sessions.pop(uid, None)


def _parse_signal_from_message(text: str) -> dict:
    """Parse the signal dict back from the signal message text."""
    from services.signals import PAIR_DISPLAY, FALLBACK_PAIR, FALLBACK_DIRECTION, FALLBACK_PAYOUT
    direction = "put" if "SELL" in text or "PUT" in text else "call"
    payout = FALLBACK_PAYOUT
    pair = FALLBACK_PAIR
    display = "EUR/USD OTC"

    import re
    # Extract pair display name
    m = re.search(r'Pair Selected:\s*\*\*([^\n*]+)\*\*', text)
    if m:
        display = m.group(1).strip()
        for k, v in PAIR_DISPLAY.items():
            if v == display:
                pair = k
                break

    # Extract payout
    m2 = re.search(r'Payout:\s*\*\*(\d+)%\*\*', text)
    if m2:
        payout = int(m2.group(1))

    return {"pair": pair, "direction": direction, "payout": payout, "display_name": display}


async def _run_all_trades(client: Client, query: CallbackQuery, user: dict, signal: dict):
    uid = user["telegram_id"]
    sessions_done = user.get("sessions_completed", 0)
    session_num = sessions_done + 1
    mode = user.get("mode", "demo")
    pair = signal["pair"]
    direction = signal["direction"]
    trade_time = user.get("trade_time", 60)
    base_amount = user.get("trade_amount", 1.0)
    max_steps = user.get("martingale_steps", 5)

    trade_results = []
    session_profit = 0.0

    for trade_num in range(1, TRADES_PER_SESSION + 1):
        # Per-trade message
        trade_msg = await query.message.reply(
            msg.msg_trade_progress(
                mode=mode, trade_num=trade_num, total_trades=TRADES_PER_SESSION,
                session_num=session_num, pair_display=signal["display_name"],
                direction=direction, steps=[], final_profit=None, balance=None,
            )
        )

        async def on_step_update(steps, _msg=trade_msg, _trade=trade_num):
            try:
                await _msg.edit_text(
                    msg.msg_trade_progress(
                        mode=mode, trade_num=_trade, total_trades=TRADES_PER_SESSION,
                        session_num=session_num, pair_display=signal["display_name"],
                        direction=direction, steps=steps, final_profit=None, balance=None,
                    )
                )
            except Exception:
                pass

        # Refresh user for latest ssid/settings
        user = await db.get_user(uid)
        ssid = user.get("ssid", "")

        result = await eng.execute_trade_with_martingale(
            telegram_id=uid, ssid=ssid,
            pair=pair, direction=direction,
            trade_time=trade_time, base_amount=base_amount,
            max_steps=max_steps, mode=mode,
            on_step_update=on_step_update,
        )

        if not result.get("success"):
            # Connection or order failed
            steps_failed = [{"step": 1, "amount": base_amount, "win": False, "profit": 0.0}]
            trade_results.append({"win": False, "profit": 0.0, "steps": steps_failed})
            await trade_msg.edit_text(
                msg.msg_trade_progress(
                    mode=mode, trade_num=trade_num, total_trades=TRADES_PER_SESSION,
                    session_num=session_num, pair_display=signal["display_name"],
                    direction=direction, steps=steps_failed,
                    final_profit=0.0, balance=user.get("demo_balance", 50000.0),
                )
            )
            continue

        net = result.get("net_profit", 0.0)
        balance = result.get("balance") or user.get("demo_balance", 50000.0)
        steps = result.get("steps", [])
        won = result.get("win", False)

        session_profit += net
        trade_results.append({"win": won, "profit": net, "steps": steps})

        # Update balance in DB
        if mode == "demo":
            await db.update_user(uid, demo_balance=float(balance or 50000.0))
        else:
            await db.update_user(uid, real_balance=float(balance or 0.0))

        # Log trade to DB
        await db.save_trade(
            telegram_id=uid, session_number=session_num, trade_number=trade_num,
            pair=pair, direction=direction, steps_taken=len(steps),
            amount=base_amount, profit=net, balance_after=float(balance or 0.0), win=won,
        )

        # Final trade message with profit
        await trade_msg.edit_text(
            msg.msg_trade_progress(
                mode=mode, trade_num=trade_num, total_trades=TRADES_PER_SESSION,
                session_num=session_num, pair_display=signal["display_name"],
                direction=direction, steps=steps,
                final_profit=net, balance=balance,
            )
        )

        await asyncio.sleep(0.5)

    # ── Session complete ───────────────────────────────────────────────────
    won_count   = sum(1 for t in trade_results if t["win"])
    lost_count  = sum(1 for t in trade_results if not t["win"])
    total_count = len(trade_results)

    # Update sessions completed
    await db.update_user(uid, sessions_completed=session_num)

    user = await db.get_user(uid)
    balance_now = user.get("demo_balance" if mode == "demo" else "real_balance", 0.0)

    await query.message.reply(
        msg.msg_session_complete(
            session_num=session_num, total_sessions=TOTAL_SESSIONS,
            won=won_count, lost=lost_count, failed=0,
            total=total_count, session_profit=session_profit,
            balance=balance_now,
        ),
        reply_markup=kb.kb_session_complete(session_num, TOTAL_SESSIONS),
    )


# ── Misc callbacks ────────────────────────────────────────────────────────────

async def cb_deposited(client: Client, query: CallbackQuery):
    await query.answer("✅ Thank you! Switch to Real mode in /settings to trade with real funds.")


async def cb_main_menu(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    user = await db.get_or_create_user(uid)
    await query.answer()
    await query.message.reply(
        msg.msg_account_status(user["mode"], user["real_balance"], user["demo_balance"]),
        reply_markup=kb.kb_main_menu(),
    )


async def cb_support(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.reply(
        "🎧 <b>Support</b>\n\nFor help, contact support via the official Pocket Option platform.",
        reply_markup=None,
    )


# ── Dummy API for signal generation without connection ────────────────────────

class _DummyApi:
    def get_assets(self):
        return {}

    def get_payout(self, pair):
        return 85

    def subscribe(self, pair, period=60):
        return True

    def get_historical_candles(self, pair, period=60, offset=9000, count_request=1):
        return None
