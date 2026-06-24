"""
plugins/start.py

Handles:
  • /start — welcome message or file delivery (single + batch)
  • verify_membership callback — re-check after user joins channels
  • Continuous membership monitoring on every message
"""

from __future__ import annotations

import asyncio

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)

from config import (
    ADMINS,
    CUSTOM_CAPTION,
    FORCE_MSG,
    FORCE_SUB_CHANNELS,
    PROTECT_CONTENT,
    REJOIN_MSG,
    START_MSG,
    LOGGER,
)
from helper_func import (
    build_join_buttons,
    decode,
    get_messages,
    verify_and_update_user,
)

logger = LOGGER(__name__)

DELETE_AFTER_SECONDS = 300  # Auto-delete shared files after 5 minutes


# ── /start ───────────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("start"))
async def start_command(client: Client, message: Message) -> None:
    user = message.from_user
    args = message.text.split()

    # ── Membership gate ──────────────────────────────────────────────────
    all_joined, missing_ids = await verify_and_update_user(
        client,
        user.id,
        user.username,
        user.first_name,
    )

    if not all_joined and user.id not in ADMINS:
        buttons = build_join_buttons(client, missing_ids)
        await message.reply(
            FORCE_MSG.format(first=user.first_name),
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True,
        )
        return

    # ── No payload → welcome message ─────────────────────────────────────
    if len(args) == 1:
        await message.reply(
            START_MSG.format(
                first=user.first_name,
                mention=user.mention,
                id=user.id,
            ),
            quote=True,
        )
        return

    # ── Decode payload ────────────────────────────────────────────────────
    try:
        payload = await decode(args[1])
    except Exception:
        await message.reply("❌ Invalid link. Please use a valid share link.")
        return

    # Expected formats: "get-<id>" or "get-<first_id>-<last_id>"
    if not payload.startswith("get-"):
        await message.reply("❌ Unknown link format.")
        return

    parts = payload[4:].split("-")  # strip "get-"

    try:
        if len(parts) == 1:
            # Single file
            message_ids = [int(parts[0])]
        elif len(parts) == 2:
            # Batch range
            first_id, last_id = int(parts[0]), int(parts[1])
            if first_id > last_id:
                first_id, last_id = last_id, first_id
            message_ids = list(range(first_id, last_id + 1))
        else:
            await message.reply("❌ Unrecognised link format.")
            return
    except ValueError:
        await message.reply("❌ Malformed link payload.")
        return

    # ── Fetch & forward messages ──────────────────────────────────────────
    messages = await get_messages(client, message_ids)

    sent: list[Message] = []
    for msg in messages:
        if msg is None or msg.empty:
            continue

        caption = (
            CUSTOM_CAPTION.format(
                previouscaption=msg.caption or "",
                filename=getattr(getattr(msg, "document", None), "file_name", ""),
            )
            if CUSTOM_CAPTION
            else (msg.caption or "")
        )

        try:
            forwarded = await msg.copy(
                chat_id=user.id,
                caption=caption,
                protect_content=PROTECT_CONTENT,
            )
            sent.append(forwarded)
        except Exception as exc:
            logger.warning("Failed to copy msg %s to user %s: %s", msg.id, user.id, exc)

    if not sent:
        await message.reply("⚠️ Could not retrieve the requested file(s). They may have been removed.")
        return

    # ── Auto-delete notice ────────────────────────────────────────────────
    notice = await message.reply(
        f"✅ <b>{len(sent)} file(s) sent.</b>\n\n"
        f"⏳ These files will be deleted in "
        f"<b>{DELETE_AFTER_SECONDS // 60} minutes</b> to prevent unauthorised redistribution.\n"
        f"Please save them before then."
    )

    # Schedule auto-delete
    asyncio.create_task(_auto_delete(sent + [notice], DELETE_AFTER_SECONDS))


# ── Verify membership callback ────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^verify_membership$"))
async def verify_membership_callback(client: Client, query: CallbackQuery) -> None:
    user = query.from_user

    all_joined, missing_ids = await verify_and_update_user(
        client,
        user.id,
        user.username,
        user.first_name,
    )

    if all_joined:
        await query.message.edit_text(
            "✅ <b>Verification successful!</b>\n\nYou can now use the bot freely. "
            "Send /start again or tap the original file link."
        )
    else:
        buttons = build_join_buttons(client, missing_ids)
        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await query.answer("❌ You still haven't joined all required channels.", show_alert=True)


# ── Continuous membership monitoring ─────────────────────────────────────────

@Client.on_message(filters.private & ~filters.command(["start"]))
async def monitor_membership(client: Client, message: Message) -> None:
    """
    Re-check membership on every private message (except /start which already
    does it). If a user has left a channel, revoke access immediately.
    """
    if not FORCE_SUB_CHANNELS:
        return

    user = message.from_user
    if user.id in ADMINS:
        return

    all_joined, missing_ids = await verify_and_update_user(
        client,
        user.id,
        user.username,
        user.first_name,
    )

    if not all_joined:
        buttons = build_join_buttons(client, missing_ids)
        await message.reply(
            REJOIN_MSG.format(first=user.first_name),
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _auto_delete(messages: list[Message], delay: int) -> None:
    """Delete a list of messages after `delay` seconds."""
    await asyncio.sleep(delay)
    for msg in messages:
        try:
            await msg.delete()
        except Exception:
            pass
