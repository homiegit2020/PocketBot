"""
handlers/settings.py
====================
/settings command — trade amount, time, martingale steps, mode.
"""

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery

from database import db
from utils import keyboards as kb
from utils import messages as msg


async def cmd_settings(client: Client, message: Message):
    uid = message.from_user.id
    user = await db.get_or_create_user(uid)
    if user.get("is_banned"):
        await message.reply(msg.msg_banned(user.get("ban_reason", "")))
        return
    await message.reply(msg.msg_settings(user), reply_markup=kb.kb_settings())


async def cb_settings(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    user = await db.get_or_create_user(uid)
    await query.answer()
    await query.message.edit_text(msg.msg_settings(user), reply_markup=kb.kb_settings())


async def cb_set_amount(client: Client, query: CallbackQuery):
    from handlers.start import _set_state
    _set_state(query.from_user.id, "await_amount")
    await query.answer()
    await query.message.reply("💵 Enter new trade amount (e.g. <code>5</code>):")


async def cb_set_time(client: Client, query: CallbackQuery):
    from handlers.start import _set_state
    _set_state(query.from_user.id, "await_trade_time")
    await query.answer()
    await query.message.reply("⏱️ Enter trade time in seconds.\nValid: 5, 10, 15, 30, 60, 120, 180, 300")


async def cb_set_martin(client: Client, query: CallbackQuery):
    from handlers.start import _set_state
    _set_state(query.from_user.id, "await_martin_steps")
    await query.answer()
    await query.message.reply("📊 Enter Martingale steps (1–10):")


async def cb_set_mode(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text("🔄 Select trading mode:", reply_markup=kb.kb_mode_select())


async def cb_mode_demo(client: Client, query: CallbackQuery):
    await db.update_user(query.from_user.id, mode="demo")
    await query.answer("✅ Demo mode activated")
    user = await db.get_user(query.from_user.id)
    await query.message.edit_text(msg.msg_settings(user), reply_markup=kb.kb_settings())


async def cb_mode_real(client: Client, query: CallbackQuery):
    await db.update_user(query.from_user.id, mode="real")
    await query.answer("✅ Real mode activated")
    user = await db.get_user(query.from_user.id)
    await query.message.edit_text(msg.msg_settings(user), reply_markup=kb.kb_settings())
