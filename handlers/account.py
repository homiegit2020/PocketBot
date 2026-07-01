"""
handlers/account.py
===================
/account command — shows account info.
"""

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery

from database import db
from utils import keyboards as kb
from utils import messages as msg


async def cmd_account(client: Client, message: Message):
    uid = message.from_user.id
    user = await db.get_or_create_user(uid)

    if user.get("is_banned"):
        await message.reply(msg.msg_banned(user.get("ban_reason", "")))
        return

    await message.reply(msg.msg_account_info(user), reply_markup=kb.kb_account())


async def cb_account(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    user = await db.get_or_create_user(uid)
    await query.answer()
    await query.message.edit_text(msg.msg_account_info(user), reply_markup=kb.kb_account())
