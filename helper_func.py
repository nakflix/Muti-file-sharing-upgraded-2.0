"""
helper_func.py

Shared utility functions: membership checks, encode/decode, message helpers.
"""

from __future__ import annotations

import asyncio
import base64
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait, UserNotParticipant

from config import ADMINS, FORCE_SUB_CHANNELS, LOGGER
from database import db

if TYPE_CHECKING:
    from pyrogram import Client
    from pyrogram.types import Message, CallbackQuery

logger = LOGGER(__name__)

_MEMBER_STATUSES = (
    ChatMemberStatus.OWNER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
)

# ── Membership verification ──────────────────────────────────────────────────

async def check_user_membership(
    client: "Client",
    user_id: int,
) -> tuple[bool, list[int]]:
    """
    Check every required channel for the given user.

    Returns
    -------
    (all_joined, missing_ids)
        all_joined  — True if the user is a member of every channel.
        missing_ids — List of channel IDs the user has NOT joined.
    """
    if not FORCE_SUB_CHANNELS:
        return True, []

    if user_id in ADMINS:
        return True, []

    missing: list[int] = []

    for ch in FORCE_SUB_CHANNELS:
        ch_id: int = ch["id"]
        try:
            member = await client.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status not in _MEMBER_STATUSES:
                missing.append(ch_id)
        except UserNotParticipant:
            missing.append(ch_id)
        except Exception as exc:
            logger.warning("Error checking membership for channel %s: %s", ch_id, exc)
            # Treat as not joined to be safe
            missing.append(ch_id)

    return len(missing) == 0, missing


async def verify_and_update_user(
    client: "Client",
    user_id: int,
    username: str | None,
    first_name: str,
) -> tuple[bool, list[int]]:
    """
    Upsert user in DB, run membership check, persist result, return status.
    """
    await db.upsert_user(user_id, username, first_name)
    all_joined, missing_ids = await check_user_membership(client, user_id)
    await db.set_verified(user_id, all_joined, missing_ids)
    return all_joined, missing_ids


def build_join_buttons(
    client_bot: "Client",
    missing_channel_ids: list[int],
) -> list[list]:
    """
    Build InlineKeyboardButton rows for channels the user hasn't joined yet.

    Requires that `client_bot` has `invite_links` dict populated at startup.
    """
    from pyrogram.types import InlineKeyboardButton

    buttons: list[list] = []
    channel_map: dict[int, dict] = {ch["id"]: ch for ch in FORCE_SUB_CHANNELS}

    for ch_id in missing_channel_ids:
        ch = channel_map.get(ch_id)
        if ch is None:
            continue

        name = ch.get("name", f"Channel {ch_id}")

        # Use stored invite link (set during bot startup)
        link = getattr(client_bot, "invite_links", {}).get(ch_id)
        if not link:
            username = ch.get("username")
            link = f"https://t.me/{username}" if username else None

        if link:
            buttons.append([InlineKeyboardButton(f"📢 Join {name}", url=link)])

    # Always append the verify button
    buttons.append(
        [InlineKeyboardButton("✅ Verify Membership", callback_data="verify_membership")]
    )

    return buttons


# ── Pyrogram subscription filter ────────────────────────────────────────────

async def _is_subscribed(filter_obj, client: "Client", update) -> bool:
    """Custom filter: passes only if the user has joined all required channels."""
    if not FORCE_SUB_CHANNELS:
        return True

    user = getattr(update, "from_user", None)
    if user is None:
        return True

    if user.id in ADMINS:
        return True

    all_joined, _ = await check_user_membership(client, user.id)
    return all_joined


subscribed = filters.create(_is_subscribed)


# ── Encode / decode (for deep-link payloads) ─────────────────────────────────

async def encode(string: str) -> str:
    string_bytes = string.encode("ascii")
    b64_bytes = base64.urlsafe_b64encode(string_bytes)
    return b64_bytes.decode("ascii").strip("=")


async def decode(b64_string: str) -> str:
    b64_string = b64_string.strip("=")
    padded = b64_string + "=" * (-len(b64_string) % 4)
    string_bytes = base64.urlsafe_b64decode(padded.encode("ascii"))
    return string_bytes.decode("ascii")


# ── Message fetch helpers ────────────────────────────────────────────────────

async def get_messages(client: "Client", message_ids: list[int]) -> list:
    messages = []
    total = 0
    while total != len(message_ids):
        batch = message_ids[total : total + 200]
        try:
            msgs = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=batch,
            )
        except FloodWait as exc:
            await asyncio.sleep(exc.value)
            msgs = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=batch,
            )
        except Exception as exc:
            logger.error("get_messages error: %s", exc)
            msgs = []
        total += len(batch)
        messages.extend(msgs)
    return messages


async def get_message_id(client: "Client", message: "Message") -> int:
    if message.forward_from_chat:
        if message.forward_from_chat.id == client.db_channel.id:
            return message.forward_from_message_id
        return 0

    if message.forward_sender_name:
        return 0

    if message.text:
        pattern = r"https://t\.me/(?:c/)?(.*)/(\d+)"
        match = re.match(pattern, message.text)
        if not match:
            return 0
        channel_id_str, msg_id_str = match.group(1), match.group(2)
        msg_id = int(msg_id_str)
        if channel_id_str.isdigit():
            if f"-100{channel_id_str}" == str(client.db_channel.id):
                return msg_id
        else:
            if channel_id_str == client.db_channel.username:
                return msg_id

    return 0


# ── Time formatting ──────────────────────────────────────────────────────────

def get_readable_time(seconds: int) -> str:
    count = 0
    up_time = ""
    time_list: list[str] = []
    suffixes = ["s", "m", "h", "days"]

    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(f"{int(result)}{suffixes[count - 1]}")
        seconds = int(remainder)

    if len(time_list) == 4:
        up_time += f"{time_list.pop()}, "
    time_list.reverse()
    up_time += ":".join(time_list)
    return up_time
