"""Async MongoDB client for document / vector storage."""

from __future__ import annotations

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_mongodb() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB is not initialized. Set MONGODB_URI and restart the API.")
    return _db


async def init_mongodb() -> None:
    global _client, _db
    uri = settings.MONGODB_URI.strip()
    if not uri:
        logger.info("mongodb_skipped reason=no_MONGODB_URI")
        return
    _client = AsyncIOMotorClient(uri)
    _db = _client.get_default_database()
    await _client.admin.command("ping")
    logger.info("mongodb_initialized database=%s", _db.name)


async def close_mongodb() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


async def ensure_mongodb_indexes() -> None:
    db = get_mongodb()
    await db.kb_documents.create_index([("owner_id", 1), ("created_at", -1)])
    await db.kb_documents.create_index([("access.visibility", 1)])
    await db.kb_documents.create_index([("access.allowed_group_ids", 1)])
    await db.kb_documents.create_index([("access.allowed_roles", 1)])
    await db.kb_chunks.create_index([("document_id", 1), ("index", 1)])
    await db.kb_chunks.create_index([("owner_id", 1)])
