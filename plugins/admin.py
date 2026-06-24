"""
plugins/admin.py

Admin-only commands: /stats, /users, /broadcast
"""

from __future__ import annotations

import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked
from pyrogram.types import Message

from config import ADMINS, BOT_STATS_TEXT, LOGGER
from database import db
from helper_func import get_readable_time
from datetime import datetime

logger = LOGGER(__name__)


@Client.on_message(filters.private & filters.command("stats") & filters.user(ADMINS))
async def stats_command(client: Client, message: Message) -> None:
    uptime = get_readable_time(int((datetime.now() - client.uptime).total_seconds()))
    total = await db.total_users()
    verified = await db.verified_users()

    await message.reply(
        f"{BOT_STATS_TEXT.format(uptime=uptime)}\n\n"
        f"👥 <b>Total users:</b> {total}\n"
        f"✅ <b>Verified users:</b> {verified}"
    )


@Client.on_message(filters.private & filters.command("users") & filters.user(ADMINS))
async def users_command(client: Client, message: Message) -> None:
    total = await db.total_users()
    verified = await db.verified_users()
    await message.reply(
        f"👥 <b>Users Summary</b>\n\n"
        f"Total: <b>{total}</b>\n"
        f"Verified: <b>{verified}</b>\n"
        f"Unverified: <b>{total - verified}</b>"
    )


@Client.on_message(filters.private & filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_command(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        await message.reply("↩️ Reply to a message with /broadcast to send it to all users.")
        return

    broadcast_msg = message.reply_to_message
    user_ids = await db.all_user_ids()

    success, failed = 0, 0
    status = await message.reply(f"📡 Broadcasting to {len(user_ids)} users…")

    for uid in user_ids:
        try:
            await broadcast_msg.copy(chat_id=uid)
            success += 1
        except FloodWait as exc:
            await asyncio.sleep(exc.value)
            try:
                await broadcast_msg.copy(chat_id=uid)
                success += 1
            except Exception:
                failed += 1
        except (InputUserDeactivated, UserIsBlocked):
            failed += 1
        except Exception as exc:
            logger.warning("Broadcast to %s failed: %s", uid, exc)
            failed += 1

        await asyncio.sleep(0.05)  # ~20 msg/s to stay within rate limits

    await status.edit(
        f"✅ <b>Broadcast complete</b>\n\n"
        f"Sent: <b>{success}</b>\n"
        f"Failed: <b>{failed}</b>"
    )
