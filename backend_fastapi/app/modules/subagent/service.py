"""User subagent registry backed by A2A Agent Cards."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.subagent.a2a_client import (
    card_display_description,
    card_display_name,
    card_skills,
    fetch_agent_card,
    normalize_agent_url,
)
from app.modules.subagent.model import UserSubagent
from app.modules.subagent.schema import (
    RegisterSubagentRequest,
    SubagentSkillSummary,
    SubagentSummary,
    UpdateSubagentRequest,
)
from app.utils.datetime import now_utc


class SubagentService:
    @staticmethod
    def _to_summary(row: UserSubagent) -> SubagentSummary:
        card = row.agent_card if isinstance(row.agent_card, dict) else {}
        capabilities = card.get("capabilities")
        streaming = bool(
            isinstance(capabilities, dict) and capabilities.get("streaming"),
        )
        skills = [
            SubagentSkillSummary(
                id=str(item.get("id") or ""),
                name=str(item.get("name") or ""),
                description=str(item.get("description") or ""),
                tags=[
                    str(tag)
                    for tag in (item.get("tags") or [])
                    if isinstance(tag, str)
                ],
            )
            for item in card_skills(card)
        ]
        return SubagentSummary(
            id=row.id,
            name=row.name,
            description=row.description,
            agent_url=row.agent_url,
            enabled=row.enabled,
            agent_version=str(card.get("version") or "") or None,
            streaming=streaming,
            skills=skills,
            last_verified_at=row.last_verified_at,
            last_error=row.last_error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_for_user(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> list[SubagentSummary]:
        statement = (
            select(UserSubagent)
            .where(UserSubagent.user_id == user_id)
            .order_by(UserSubagent.updated_at.desc())
        )
        result = await session.exec(statement)
        return [self._to_summary(row) for row in result.all()]

    async def register(
        self,
        session: AsyncSession,
        user_id: UUID,
        body: RegisterSubagentRequest,
    ) -> SubagentSummary:
        agent_url = normalize_agent_url(str(body.agent_url))
        try:
            card = await fetch_agent_card(agent_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        now = now_utc()
        row = UserSubagent(
            user_id=user_id,
            name=card_display_name(card, body.name),
            description=card_display_description(card, body.description),
            agent_url=agent_url,
            agent_card=card,
            enabled=True,
            last_verified_at=now,
            last_error=None,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="This agent URL is already registered",
            ) from exc
        await session.refresh(row)
        return self._to_summary(row)

    async def refresh(
        self,
        session: AsyncSession,
        user_id: UUID,
        subagent_id: UUID,
    ) -> SubagentSummary:
        row = await self._require_owned(session, user_id, subagent_id)
        try:
            card = await fetch_agent_card(row.agent_url)
        except ValueError as exc:
            row.last_error = str(exc)[:4000]
            row.updated_at = now_utc()
            session.add(row)
            await session.commit()
            await session.refresh(row)
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        row.agent_card = card
        row.name = card_display_name(card, row.name)
        if not row.description:
            row.description = card_display_description(card)
        row.last_verified_at = now_utc()
        row.last_error = None
        row.updated_at = now_utc()
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return self._to_summary(row)

    async def update(
        self,
        session: AsyncSession,
        user_id: UUID,
        subagent_id: UUID,
        body: UpdateSubagentRequest,
    ) -> SubagentSummary:
        row = await self._require_owned(session, user_id, subagent_id)
        if body.enabled is not None:
            row.enabled = body.enabled
        if body.name is not None:
            row.name = body.name.strip()
        if body.description is not None:
            row.description = body.description.strip()
        row.updated_at = now_utc()
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return self._to_summary(row)

    async def delete(
        self,
        session: AsyncSession,
        user_id: UUID,
        subagent_id: UUID,
    ) -> None:
        row = await self._require_owned(session, user_id, subagent_id)
        await session.delete(row)
        await session.commit()

    async def _require_owned(
        self,
        session: AsyncSession,
        user_id: UUID,
        subagent_id: UUID,
    ) -> UserSubagent:
        row = await session.get(UserSubagent, subagent_id)
        if row is None or row.user_id != user_id:
            raise HTTPException(status_code=404, detail="Subagent not found")
        return row


subagent_service = SubagentService()
