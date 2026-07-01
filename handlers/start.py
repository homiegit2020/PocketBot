"""
handlers/start.py
=================
/start command — new & existing account flows.
Manages conversation state via user DB flags.
"""

import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

from database import db
from services.pocket_auth import create_pocket_option_account, login_pocket_option_account
from utils import keyboards as kb
from utils import messages as msg
from utils.logger import log, log_error

# ── Simple in-memory FSM ──────────────────────────────────────────────────────
# state: None | "await_new_email" | "await_existing_email" | "await_password"
_user_state: dict[int, str] = {}
_user_temp:  dict[int, dict] = {}   # temporary data during flow


def _set_state(uid: int, state: str | None):
    if state is None:
        _user_state.pop(uid, None)
    else:
        _user_state[uid] = state


def get_state(uid: int) -> str | None:
    return _user_state.get(uid)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(client: Client, message: Message):
    uid = message.from_user.id
    user = await db.get_or_create_user(uid)
    await db.log_activity(uid, "start", "")

    if user.get("is_banned"):
        await message.reply(msg.msg_banned(user.get("ban_reason", "")))
        return

    _set_state(uid, None)

    await message.reply(msg.msg_welcome(), reply_markup=kb.kb_welcome())
    await asyncio.sleep(0.5)
    await message.reply(msg.msg_has_account_question(), reply_markup=kb.kb_has_account())


# ── Callback: has_account / new_account ──────────────────────────────────────

async def cb_has_account(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    user = await db.get_user(uid)
    if not user:
        user = await db.create_user(uid)

    if user.get("is_banned"):
        await query.answer(text="🚫 You are banned.", show_alert=True)
        return

    _set_state(uid, "await_existing_email")
    await query.answer()
    await query.message.reply(msg.msg_ask_email_existing())


async def cb_new_account(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    if not await db.get_user(uid):
        await db.create_user(uid)
    user = await db.get_user(uid)

    if user.get("is_banned"):
        await query.answer(text="🚫 You are banned.", show_alert=True)
        return

    _set_state(uid, "await_new_email")
    await query.answer()
    await query.message.reply(msg.msg_ask_email())


# ── Text handler — email / password inputs ────────────────────────────────────

async def handle_text_input(client: Client, message: Message):
    uid = message.from_user.id
    state = get_state(uid)

    if state is None:
        return  # not in a flow

    user = await db.get_user(uid)
    if user and user.get("is_banned"):
        await message.reply(msg.msg_banned(user.get("ban_reason", "")))
        return

    text = message.text.strip()

    # ── NEW ACCOUNT: waiting for email ──────────────────────────────────────
    if state == "await_new_email":
        if "@" not in text or "." not in text:
            await message.reply("⚠️ That doesn't look like a valid email. Please try again.")
            return

        _set_state(uid, None)
        loading = await message.reply("⏳ <b>Creating your account...</b>")

        await asyncio.sleep(1)
        await loading.edit_text("⏳ <b>Setting up your profile...</b>")
        await asyncio.sleep(1)
        await loading.edit_text("⏳ <b>Configuring trading access...</b>")

        result = await create_pocket_option_account(text)

        if result.get("success"):
            await db.update_user(uid,
                email=result["email"],
                password=result["password"],
                account_id=result.get("account_id", ""),
                po_session=result.get("po_session", ""),
                po_uid=result.get("po_uid", ""),
                ssid=result.get("ssid", ""),
                demo_balance=result.get("demo_balance", 50000.0),
                real_balance=result.get("real_balance", 0.0),
            )
            user = await db.get_user(uid)
            await db.log_activity(uid, "register", f"email={text}")

            await loading.edit_text(
                msg.msg_access_confirmed(result.get("account_id", ""), result["email"])
            )
            await asyncio.sleep(1)
            await message.reply(
                msg.msg_account_status("demo", user["real_balance"], user["demo_balance"]),
                reply_markup=kb.kb_start_trade(),
            )
        else:
            await loading.edit_text(
                f"⚠️ Could not create account.\n\n"
                f"{result.get('error', '')}\n\n"
                "Please try a different email or use /start"
            )

    # ── EXISTING ACCOUNT: waiting for email ─────────────────────────────────
    elif state == "await_existing_email":
        if "@" not in text or "." not in text:
            await message.reply("⚠️ That doesn't look like a valid email. Please try again.")
            return

        _user_temp[uid] = {"email": text}
        _set_state(uid, "await_password")
        await message.reply(msg.msg_ask_password())

    # ── EXISTING ACCOUNT: waiting for password ───────────────────────────────
    elif state == "await_password":
        temp = _user_temp.get(uid, {})
        email = temp.get("email", "")
        password = text

        if not email:
            _set_state(uid, None)
            await message.reply("Something went wrong. Please use /start again.")
            return

        _set_state(uid, None)
        _user_temp.pop(uid, None)

        loading = await message.reply(msg.msg_logging_in())
        await asyncio.sleep(1)

        result = await login_pocket_option_account(email, password)

        if result.get("success"):
            await db.update_user(uid,
                email=email,
                password=password,
                account_id=result.get("account_id", ""),
                po_session=result.get("po_session", ""),
                po_uid=result.get("po_uid", ""),
                ssid=result.get("ssid", ""),
                demo_balance=result.get("demo_balance", 50000.0),
                real_balance=result.get("real_balance", 0.0),
            )
            user = await db.get_user(uid)
            await db.log_activity(uid, "login", f"email={email}")

            await loading.edit_text(
                msg.msg_access_confirmed(result.get("account_id", ""), email)
            )
            await asyncio.sleep(1)
            await message.reply(
                msg.msg_account_status("demo", user["real_balance"], user["demo_balance"]),
                reply_markup=kb.kb_start_trade(),
            )
        else:
            await loading.edit_text(
                f"❌ Login failed.\n\n{result.get('error', 'Check your email and password.')}"
            )

    # ── Settings input states ────────────────────────────────────────────────
    elif state == "await_amount":
        try:
            amount = float(text.replace("$", "").replace(",", ""))
            if amount < 1:
                raise ValueError("min $1")
            await db.update_user(uid, trade_amount=amount)
            _set_state(uid, None)
            user = await db.get_user(uid)
            await message.reply(
                f"✅ Trade amount set to ${amount:.2f}",
                reply_markup=kb.kb_settings(),
            )
        except ValueError:
            await message.reply("⚠️ Invalid amount. Enter a number ≥ 1 (e.g. 5)")

    elif state == "await_martin_steps":
        try:
            steps = int(text)
            if not 1 <= steps <= 10:
                raise ValueError
            await db.update_user(uid, martingale_steps=steps)
            _set_state(uid, None)
            await message.reply(
                f"✅ Martingale steps set to {steps}",
                reply_markup=kb.kb_settings(),
            )
        except ValueError:
            await message.reply("⚠️ Enter a number between 1 and 10")

    elif state == "await_trade_time":
        valid_times = [5, 10, 15, 30, 60, 120, 180, 300]
        try:
            t = int(text.replace("s", "").replace("sec", "").strip())
            if t not in valid_times:
                raise ValueError
            await db.update_user(uid, trade_time=t)
            _set_state(uid, None)
            await message.reply(
                f"✅ Trade time set to {t}s",
                reply_markup=kb.kb_settings(),
            )
        except ValueError:
            await message.reply(f"⚠️ Choose from: {', '.join(str(v)+'s' for v in valid_times)}")

    # ── Admin broadcast ──────────────────────────────────────────────────────
    elif state == "await_broadcast_msg":
        _set_state(uid, None)
        await _do_broadcast(client, uid, text, message)

    # ── Admin search ─────────────────────────────────────────────────────────
    elif state == "await_search":
        _set_state(uid, None)
        await _do_search(client, uid, text, message)

    # ── Admin message to user ────────────────────────────────────────────────
    elif state.startswith("await_admin_msg_"):
        target_id = int(state.split("_")[-1])
        _set_state(uid, None)
        try:
            await client.send_message(target_id, f"📨 <b>Message from Admin:</b>\n\n{text}")
            await message.reply("✅ Message sent.")
        except Exception as e:
            await message.reply(f"❌ Failed to send: {e}")


async def _do_broadcast(client: Client, admin_id: int, text: str, message: Message):
    users = await db.get_all_users()
    sent = 0
    failed = 0
    for u in users:
        try:
            await client.send_message(u["telegram_id"], text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await message.reply(f"📢 Broadcast done: ✅ {sent} sent, ❌ {failed} failed")


async def _do_search(client: Client, admin_id: int, query: str, message: Message):
    from handlers.admin import _format_user_detail
    user = None
    if query.isdigit():
        user = await db.get_user(int(query))
    else:
        user = await db.search_user_by_email(query)

    if user:
        await message.reply(_format_user_detail(user), reply_markup=kb.kb_admin_user(user["telegram_id"], user["is_banned"]))
    else:
        await message.reply("❌ User not found.")
