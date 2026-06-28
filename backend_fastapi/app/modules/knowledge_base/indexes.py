"""MongoDB index setup for the knowledge base module."""

from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create indexes used by knowledge base queries."""
    await db.kb_documents.create_index([("owner_id", 1), ("created_at", -1)])
    await db.kb_documents.create_index([("access.visibility", 1)])
    await db.kb_documents.create_index([("access.allowed_group_ids", 1)])
    await db.kb_documents.create_index([("access.allowed_roles", 1)])
    await db.kb_chunks.create_index([("document_id", 1), ("index", 1)])
    await db.kb_chunks.create_index([("owner_id", 1)])
