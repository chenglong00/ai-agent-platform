"""User long-term memory persistence and prompt formatting."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.memory.model import MemoryCategory, MemorySource, UserMemory
from app.modules.memory.schema import CreateMemoryRequest, MemorySummary, UpdateMemoryRequest
from app.utils.datetime import now_utc

_CATEGORY_LABELS = {
    MemoryCategory.FACT: "Fact",
    MemoryCategory.PREFERENCE: "Preference",
    MemoryCategory.PROFILE: "Profile",
    MemoryCategory.GOAL: "Goal",
    MemoryCategory.OTHER: "Note",
}


def _normalize_content(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip().lower())


def parse_memory_category(raw: str) -> MemoryCategory:
    try:
        return MemoryCategory(raw.strip().lower())
    except ValueError:
        return MemoryCategory.OTHER


def _parse_category(raw: str) -> MemoryCategory:
    return parse_memory_category(raw)


class MemoryService:
    async def list_for_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        limit: int = 100,
    ) -> list[MemorySummary]:
        statement = (
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .order_by(UserMemory.updated_at.desc())
            .limit(max(limit, 1))
        )
        result = await session.exec(statement)
        return [MemorySummary.model_validate(row) for row in result.all()]

    async def search_for_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        query: str,
        *,
        limit: int = 10,
    ) -> list[MemorySummary]:
        needle = query.strip()
        if not needle:
            return await self.list_for_user(session, user_id, limit=limit)

        pattern = f"%{needle}%"
        statement = (
            select(UserMemory)
            .where(
                UserMemory.user_id == user_id,
                UserMemory.content.ilike(pattern),
            )
            .order_by(UserMemory.updated_at.desc())
            .limit(max(limit, 1))
        )
        result = await session.exec(statement)
        return [MemorySummary.model_validate(row) for row in result.all()]

    async def upsert_memory(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        category: MemoryCategory,
        content: str,
        source: MemorySource = MemorySource.AGENT,
        conversation_id: UUID | None = None,
    ) -> MemorySummary:
        cleaned = content.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Memory content cannot be empty")

        normalized = _normalize_content(cleaned)
        statement = select(UserMemory).where(UserMemory.user_id == user_id)
        result = await session.exec(statement)
        existing: UserMemory | None = None
        for row in result.all():
            if _normalize_content(row.content) == normalized:
                existing = row
                break

        now = now_utc()
        if existing is not None:
            existing.category = category
            existing.content = cleaned
            existing.source = source
            existing.conversation_id = conversation_id or existing.conversation_id
            existing.updated_at = now
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
            return MemorySummary.model_validate(existing)

        row = UserMemory(
            user_id=user_id,
            category=category,
            content=cleaned,
            source=source,
            conversation_id=conversation_id,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return MemorySummary.model_validate(row)

    async def create_memory(
        self,
        session: AsyncSession,
        user_id: UUID,
        body: CreateMemoryRequest,
    ) -> MemorySummary:
        return await self.upsert_memory(
            session,
            user_id,
            category=body.category,
            content=body.content,
            source=MemorySource.USER,
        )

    async def update_memory(
        self,
        session: AsyncSession,
        user_id: UUID,
        memory_id: UUID,
        body: UpdateMemoryRequest,
    ) -> MemorySummary:
        row = await self._require_owned(session, user_id, memory_id)
        if body.category is not None:
            row.category = body.category
        if body.content is not None:
            row.content = body.content.strip()
        row.updated_at = now_utc()
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return MemorySummary.model_validate(row)

    async def delete_memory(
        self,
        session: AsyncSession,
        user_id: UUID,
        memory_id: UUID,
    ) -> None:
        row = await self._require_owned(session, user_id, memory_id)
        await session.delete(row)
        await session.commit()

    async def build_prompt_context(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        limit: int = 20,
    ) -> str:
        rows = await self.list_for_user(session, user_id, limit=limit)
        if not rows:
            return ""

        lines = [
            "[Long-term memory about this user — use to personalize replies; "
            "do not mention this block unless the user asks about memory]"
        ]
        for row in reversed(rows):
            label = _CATEGORY_LABELS.get(row.category, "Note")
            lines.append(f"- ({label}) {row.content}")
        return "\n".join(lines)

    async def _require_owned(
        self,
        session: AsyncSession,
        user_id: UUID,
        memory_id: UUID,
    ) -> UserMemory:
        row = await session.get(UserMemory, memory_id)
        if row is None or row.user_id != user_id:
            raise HTTPException(status_code=404, detail="Memory not found")
        return row


memory_service = MemoryService()
