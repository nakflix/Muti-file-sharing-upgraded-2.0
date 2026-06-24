"""
database/mongodb.py

Async MongoDB layer powered by Motor.
Stores user records: verification status, missing channels, timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import motor.motor_asyncio

from config import DB_NAME, DB_URI, LOGGER

logger = LOGGER(__name__)


class Database:
    """Thin async wrapper around the Motor MongoDB client."""

    def __init__(self) -> None:
        self._client: motor.motor_asyncio.AsyncIOMotorClient | None = None
        self._db = None
        self._users = None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def connect(self) -> None:
        self._client = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
        self._db = self._client[DB_NAME]
        self._users = self._db["users"]

        # Ensure indexes
        await self._users.create_index("user_id", unique=True)
        logger.info("MongoDB connected (database: %s)", DB_NAME)

    async def close(self) -> None:
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed.")

    # ── User operations ──────────────────────────────────────────────────

    async def upsert_user(
        self,
        user_id: int,
        username: str | None,
        first_name: str,
    ) -> None:
        """Insert the user if they don't exist; update name fields if they do."""
        await self._users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "username": username,
                    "first_name": first_name,
                    "last_seen": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "verified": False,
                    "missing_channels": [],
                    "joined_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )

    async def set_verified(
        self,
        user_id: int,
        verified: bool,
        missing_channels: list[int],
    ) -> None:
        await self._users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "verified": verified,
                    "missing_channels": missing_channels,
                    "last_verified": datetime.now(timezone.utc),
                }
            },
        )

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        return await self._users.find_one({"user_id": user_id}, {"_id": 0})

    async def total_users(self) -> int:
        return await self._users.count_documents({})

    async def verified_users(self) -> int:
        return await self._users.count_documents({"verified": True})

    async def all_user_ids(self) -> list[int]:
        cursor = self._users.find({}, {"user_id": 1, "_id": 0})
        return [doc["user_id"] async for doc in cursor]
