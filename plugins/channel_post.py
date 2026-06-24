"""
plugins/channel_post.py

Handles two features ported from nakflix/muti-file-sharing:

1. AUTO LINK GENERATION — When a new post appears in the DB channel the bot
   automatically edits or replies with a shareable deep-link so the owner
   never has to run a command.

2. /batch <first_id> <last_id> — Admin command that generates a single
   deep-link covering a range of messages (batch files). Users who click
   it get every file in that range forwarded to them in one shot.
"""

from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMINS, CHANNEL_ID, DISABLE_CHANNEL_BUTTON, LOGGER
from helper_func import encode, get_message_id

logger = LOGGER(__name__)


# ── 1. Auto-link on every new DB-channel post ────────────────────────────────

@Client.on_message(filters.channel & filters.incoming)
async def new_channel_post(client: Client, message: Message) -> None:
    """
    Whenever a file (or any message) is posted to the DB channel, generate a
    shareable deep-link and append it as a reply button on the post.
    """
    # Only react to posts in *our* DB channel
    if message.chat.id != client.db_channel.id:
        return

    # Build the encoded payload: "get-<msg_id>"
    encoded = await encode(f"get-{message.id}")
    share_link = f"https://t.me/{client.username}?start={encoded}"

    # Optionally suppress the share button via env var
    if DISABLE_CHANNEL_BUTTON:
        return

    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔗 Get File", url=share_link)]]
    )

    try:
        await message.reply_markup_edit(reply_markup)
    except Exception:
        # reply_markup_edit may not exist on older pyrogram; fall back to reply
        try:
            await message.reply(
                f"<b>🔗 Share Link:</b>\n<code>{share_link}</code>",
                reply_markup=reply_markup,
                quote=True,
            )
        except Exception as exc:
            logger.warning("Auto-link reply failed for msg %s: %s", message.id, exc)


# ── 2. /batch command ────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("batch") & filters.user(ADMINS))
async def batch_command(client: Client, message: Message) -> None:
    """
    Usage: /batch <first_msg_id> <last_msg_id>

    Forwards a message range from the DB channel to whoever starts the bot
    with the generated deep-link.  Only admins can run this command.
    """
    args = message.text.split()
    if len(args) != 3:
        await message.reply(
            "<b>Usage:</b> <code>/batch &lt;first_id&gt; &lt;last_id&gt;</code>\n\n"
            "Forward the first and last messages from the DB channel, "
            "or send the Telegram post links, then use this command with their IDs."
        )
        return

    # ── Accept either a raw integer or a forwarded-message ID ──────────

    first_raw, last_raw = args[1], args[2]

    # Try resolving as raw integers first
    try:
        first_id = int(first_raw)
    except ValueError:
        await message.reply("❌ <code>first_id</code> must be an integer.")
        return

    try:
        last_id = int(last_raw)
    except ValueError:
        await message.reply("❌ <code>last_id</code> must be an integer.")
        return

    if first_id > last_id:
        first_id, last_id = last_id, first_id

    # Verify the IDs exist in the DB channel
    try:
        msgs = await client.get_messages(
            chat_id=client.db_channel.id,
            message_ids=[first_id, last_id],
        )
        if any(m is None or m.empty for m in msgs):
            await message.reply(
                "❌ One or both message IDs were not found in the DB channel.\n"
                "Make sure the IDs belong to messages in the correct channel."
            )
            return
    except Exception as exc:
        await message.reply(f"❌ Failed to verify message IDs: {exc}")
        return

    # Encode as "get-<first>-<last>"
    encoded = await encode(f"get-{first_id}-{last_id}")
    share_link = f"https://t.me/{client.username}?start={encoded}"

    file_count = last_id - first_id + 1
    await message.reply(
        f"✅ <b>Batch link generated!</b>\n\n"
        f"📦 Files: <b>{file_count}</b> "
        f"(IDs {first_id} → {last_id})\n\n"
        f"🔗 <b>Share Link:</b>\n<code>{share_link}</code>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 Open Link", url=share_link)]]
        ),
    )
    logger.info(
        "Admin %s generated batch link: %s → %s (%d files)",
        message.from_user.id,
        first_id,
        last_id,
        file_count,
    )


# ── 3. Helper: generate link from forwarded message ──────────────────────────

@Client.on_message(
    filters.private
    & filters.user(ADMINS)
    & (filters.forwarded | filters.text)
    & ~filters.command(["start", "batch", "stats", "users", "broadcast"])
)
async def get_link_from_forward(client: Client, message: Message) -> None:
    """
    Admin shortcut: forward a message from the DB channel (or paste its link)
    and the bot replies with a shareable deep-link for that single file.
    """
    msg_id = await get_message_id(client, message)
    if not msg_id:
        return  # Not from the DB channel — ignore silently

    encoded = await encode(f"get-{msg_id}")
    share_link = f"https://t.me/{client.username}?start={encoded}"

    await message.reply(
        f"✅ <b>Share Link for message {msg_id}:</b>\n\n"
        f"<code>{share_link}</code>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 Open Link", url=share_link)]]
        ),
    )
