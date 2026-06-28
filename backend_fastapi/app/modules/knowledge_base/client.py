"""MongoDB client for the knowledge base module."""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.modules.knowledge_base.indexes import ensure_indexes

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_mongodb() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB is not configured. Set MONGODB_URI and restart the API.")
    return _db


async def init_mongodb() -> None:
    global _client, _db
    uri = settings.MONGODB_URI.strip()
    if not uri:
        logger.info("knowledge_base_mongodb_skipped reason=no_MONGODB_URI")
        return
    _client = AsyncIOMotorClient(uri)
    _db = _client.get_default_database()
    await _client.admin.command("ping")
    logger.info("knowledge_base_mongodb_initialized database=%s", _db.name)
    await ensure_indexes(_db)


async def close_mongodb() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
