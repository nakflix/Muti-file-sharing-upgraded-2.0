"""
config.py — Central configuration for the File-Sharing Bot.

All sensitive values are loaded from environment variables so you never
hardcode secrets. Required channels are stored as a JSON list so you can
add / remove channels without touching any other file.
"""

import os
import json
import logging
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

load_dotenv()

# ── Telegram credentials ────────────────────────────────────────────────────
TG_BOT_TOKEN: str = os.environ["TG_BOT_TOKEN"]
APP_ID: int = int(os.environ["APP_ID"])
API_HASH: str = os.environ["API_HASH"]

# ── Bot internals ────────────────────────────────────────────────────────────
TG_BOT_WORKERS: int = int(os.environ.get("TG_BOT_WORKERS", "4"))
PORT: str = os.environ.get("PORT", "8089")

# ── Owner / admins ───────────────────────────────────────────────────────────
OWNER_ID: int = int(os.environ["OWNER_ID"])
_extra_admins_raw = os.environ.get("ADMINS", "")
ADMINS: list[int] = [OWNER_ID]
if _extra_admins_raw:
    for _a in _extra_admins_raw.split():
        try:
            ADMINS.append(int(_a))
        except ValueError:
            raise ValueError(f"ADMINS contains a non-integer value: {_a!r}")

# ── Database channel (stores shared files) ────────────────────────────────
CHANNEL_ID: int = int(os.environ["CHANNEL_ID"])

# ── MongoDB ──────────────────────────────────────────────────────────────────
DB_URI: str = os.environ["DATABASE_URL"]          # full MongoDB connection string
DB_NAME: str = os.environ.get("DATABASE_NAME", "fileshare_bot")

# ── Required / force-subscribe channels ─────────────────────────────────────
# Format (env var FORCE_SUB_CHANNELS): JSON array of objects, e.g.
# '[{"id": -1001234567890, "name": "My Channel", "username": "mychannel"}]'
# "username" is used to build an invite URL when the channel is public;
# for private channels leave "username" blank and the bot will use the stored
# invite link.
_FORCE_SUB_RAW = os.environ.get("FORCE_SUB_CHANNELS", "[]")
try:
    FORCE_SUB_CHANNELS: list[dict] = json.loads(_FORCE_SUB_RAW)
except json.JSONDecodeError as exc:
    raise ValueError(
        "FORCE_SUB_CHANNELS must be valid JSON. "
        "Example: '[{\"id\":-1001234567890,\"name\":\"My Chan\"}]'"
    ) from exc

# ── Messages (customisable) ──────────────────────────────────────────────────
START_MSG: str = os.environ.get(
    "START_MESSAGE",
    "<b>Hello {first}! 👋\nWelcome to the file-sharing bot.</b>",
)

FORCE_MSG: str = os.environ.get(
    "FORCE_SUB_MESSAGE",
    (
        "<b>Hello {first}! 👋</b>\n\n"
        "You must join all required channels before using this bot.\n"
        "Please join the channel(s) below, then press <b>✅ Verify Membership</b>."
    ),
)

REJOIN_MSG: str = os.environ.get(
    "REJOIN_MESSAGE",
    (
        "<b>⚠️ Access Revoked</b>\n\n"
        "Hi {first}, you have left one or more required channels.\n"
        "Please rejoin the channel(s) below and press <b>✅ Verify Membership</b>."
    ),
)

CUSTOM_CAPTION: str | None = os.environ.get("CUSTOM_CAPTION") or None
PROTECT_CONTENT: bool = os.environ.get("PROTECT_CONTENT", "False") == "True"
DISABLE_CHANNEL_BUTTON: bool = os.environ.get("DISABLE_CHANNEL_BUTTON", "False") == "True"

BOT_STATS_TEXT: str = "<b>BOT UPTIME</b>\n{uptime}"

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_FILE_NAME = "logs.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE_NAME, maxBytes=50_000_000, backupCount=10),
        logging.StreamHandler(),
    ],
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
