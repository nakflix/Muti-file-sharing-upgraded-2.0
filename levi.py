"""
levi.py

Bot client: starts Pyrogram, pre-fetches invite links for every required
channel, verifies the DB channel, and launches the aiohttp web server.
"""

from __future__ import annotations

import sys
from datetime import datetime

from aiohttp import web
from pyrogram import Client
from pyrogram.enums import ParseMode

from config import (
    API_HASH,
    APP_ID,
    CHANNEL_ID,
    FORCE_SUB_CHANNELS,
    LOGGER,
    PORT,
    TG_BOT_TOKEN,
    TG_BOT_WORKERS,
)
from database import db
from plugins import web_server

import pyromod.listen  # noqa: F401  (patches Client with .listen())

logger = LOGGER(__name__)


class Bot(Client):

    def __init__(self) -> None:
        super().__init__(
            name="Bot",
            api_hash=API_HASH,
            api_id=APP_ID,
            plugins={"root": "plugins"},
            workers=TG_BOT_WORKERS,
            bot_token=TG_BOT_TOKEN,
        )
        self.LOGGER = LOGGER

        # Maps channel_id → invite_link string
        self.invite_links: dict[int, str] = {}
        self.uptime: datetime | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        await super().start()
        self.uptime = datetime.now()

        # Connect MongoDB
        await db.connect()

        # Collect invite links for every force-sub channel
        for ch in FORCE_SUB_CHANNELS:
            ch_id: int = ch["id"]
            ch_name: str = ch.get("name", str(ch_id))
            try:
                chat = await self.get_chat(ch_id)
                link = chat.invite_link
                if not link:
                    link = await self.export_chat_invite_link(ch_id)
                self.invite_links[ch_id] = link
                logger.info("Invite link ready for '%s': %s", ch_name, link)
            except Exception as exc:
                logger.warning(
                    "Cannot fetch invite link for channel '%s' (%s): %s",
                    ch_name,
                    ch_id,
                    exc,
                )
                logger.warning(
                    "Ensure the bot is an admin with 'Invite users via link' permission "
                    "in that channel."
                )
                sys.exit(1)

        # Verify DB channel access
        try:
            db_chat = await self.get_chat(CHANNEL_ID)
            self.db_channel = db_chat
            probe = await self.send_message(chat_id=db_chat.id, text="Bot started ✅")
            await probe.delete()
            logger.info("DB channel verified: %s", db_chat.title)
        except Exception as exc:
            logger.warning("Cannot access DB channel (%s): %s", CHANNEL_ID, exc)
            logger.warning(
                "Make sure the bot is an admin in the DB channel and CHANNEL_ID is correct."
            )
            sys.exit(1)

        me = await self.get_me()
        self.username = me.username

        self.set_parse_mode(ParseMode.HTML)
        logger.info("Bot @%s is running!", self.username)

        # Start aiohttp keep-alive server
        runner = web.AppRunner(await web_server())
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()

    async def stop(self, *args) -> None:
        await db.close()
        await super().stop()
        logger.info("Bot stopped.")
