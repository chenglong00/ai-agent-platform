"""Agent skills persistence and access control (PostgreSQL)."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.knowledge_base.access import UserAccessContext, validate_access_for_user
from app.modules.knowledge_base.schema import (
    AccessVisibilityOption,
    GroupOption,
    RoleOption,
)
from app.modules.skills.access import can_manage_skill, can_read_skill, parse_skill_access
from app.modules.skills.model import AgentSkill
from app.modules.skills.schema import (
    CreateSkillRequest,
    DeleteSkillResponse,
    SkillDetail,
    SkillOptionsResponse,
    SkillSummary,
    UpdateSkillRequest,
)

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")

ACCESS_VISIBILITY_OPTIONS: list[AccessVisibilityOption] = [
    AccessVisibilityOption(
        id="private",
        label="Private",
        description="Only you can view and edit this skill.",
    ),
    AccessVisibilityOption(
        id="organization",
        label="Organization",
        description="Any signed-in user can use this skill.",
    ),
    AccessVisibilityOption(
        id="group",
        label="Groups",
        description="Members of selected groups can use this skill.",
    ),
    AccessVisibilityOption(
        id="role",
        label="Roles",
        description="Users with selected platform roles can use this skill.",
    ),
]

ROLE_OPTIONS: list[RoleOption] = [
    RoleOption(id="OWNER", label="Owner"),
    RoleOption(id="ADMIN", label="Admin"),
    RoleOption(id="MEMBER", label="Member"),
]


def slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug[:80] or "skill"


def _parse_skill_id(skill_id: str) -> UUID:
    try:
        return UUID(skill_id.strip())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Skill not found") from exc


class SkillsService:
    def options(self, groups: list[GroupOption] | None = None) -> SkillOptionsResponse:
        return SkillOptionsResponse(
            access_visibility_options=ACCESS_VISIBILITY_OPTIONS,
            role_options=ROLE_OPTIONS,
            groups=groups or [],
        )

    async def _get_skill_row(
        self,
        session: AsyncSession,
        skill_id: str,
    ) -> AgentSkill | None:
        parsed_id = _parse_skill_id(skill_id)
        return await session.get(AgentSkill, parsed_id)

    async def _get_for_read(
        self,
        session: AsyncSession,
        ctx: UserAccessContext,
        skill_id: str,
    ) -> AgentSkill:
        skill = await self._get_skill_row(session, skill_id)
        if skill is None or not can_read_skill(ctx, skill):
            raise HTTPException(status_code=404, detail="Skill not found")
        return skill

    async def _get_for_manage(
        self,
        session: AsyncSession,
        ctx: UserAccessContext,
        skill_id: str,
    ) -> AgentSkill:
        skill = await self._get_skill_row(session, skill_id)
        if skill is None or not can_manage_skill(ctx, skill):
            raise HTTPException(status_code=404, detail="Skill not found")
        return skill

    def _to_summary(self, ctx: UserAccessContext, skill: AgentSkill) -> SkillSummary:
        return SkillSummary(
            id=str(skill.id),
            slug=skill.slug,
            name=skill.name,
            description=skill.description,
            source="custom",
            enabled=skill.enabled,
            access=parse_skill_access(skill),
            is_owner=can_manage_skill(ctx, skill),
            created_at=skill.created_at,
            updated_at=skill.updated_at,
        )

    async def list_skills(
        self,
        session: AsyncSession,
        ctx: UserAccessContext,
    ) -> list[SkillSummary]:
        result = await session.exec(
            select(AgentSkill).order_by(AgentSkill.created_at.desc()),
        )
        return [
            self._to_summary(ctx, skill)
            for skill in result.all()
            if can_read_skill(ctx, skill)
        ]

    async def get_skill(
        self,
        session: AsyncSession,
        ctx: UserAccessContext,
        skill_id: str,
    ) -> SkillDetail:
        skill = await self._get_for_read(session, ctx, skill_id)
        summary = self._to_summary(ctx, skill)
        return SkillDetail(
            **summary.model_dump(),
            content=skill.content,
            can_manage=can_manage_skill(ctx, skill),
        )

    async def read_skill_content(
        self,
        session: AsyncSession,
        ctx: UserAccessContext,
        skill_id: str,
    ) -> str:
        skill = await self._get_for_read(session, ctx, skill_id)
        if not skill.enabled:
            raise HTTPException(status_code=404, detail="Skill is disabled")
        header = f"# {skill.name}\n\n{skill.description.strip()}\n\n"
        return header + skill.content.strip()

    async def _ensure_unique_slug(
        self,
        session: AsyncSession,
        owner_id: UUID,
        slug: str,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        statement = select(AgentSkill).where(
            AgentSkill.owner_id == owner_id,
            AgentSkill.slug == slug,
        )
        if exclude_id is not None:
            statement = statement.where(AgentSkill.id != exclude_id)
        result = await session.exec(statement)
        if result.first() is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Skill slug '{slug}' is already in use. Choose another name or slug.",
            )

    async def create_skill(
        self,
        session: AsyncSession,
        ctx: UserAccessContext,
        body: CreateSkillRequest,
    ) -> SkillDetail:
        try:
            validate_access_for_user(ctx, body.access)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        slug = slugify(body.slug or body.name)
        await self._ensure_unique_slug(session, ctx.user_id, slug)

        now = datetime.now(UTC)
        skill = AgentSkill(
            id=uuid4(),
            owner_id=ctx.user_id,
            slug=slug,
            name=body.name.strip(),
            description=body.description.strip(),
            content=body.content.strip(),
            enabled=body.enabled,
            access=body.access.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
        )
        session.add(skill)
        await session.commit()
        await session.refresh(skill)
        return await self.get_skill(session, ctx, str(skill.id))

    async def update_skill(
        self,
        session: AsyncSession,
        ctx: UserAccessContext,
        skill_id: str,
        body: UpdateSkillRequest,
    ) -> SkillDetail:
        skill = await self._get_for_manage(session, ctx, skill_id)

        if body.name is not None:
            skill.name = body.name
        if body.description is not None:
            skill.description = body.description
        if body.content is not None:
            skill.content = body.content
        if body.enabled is not None:
            skill.enabled = body.enabled
        if body.access is not None:
            try:
                validate_access_for_user(ctx, body.access)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            skill.access = body.access.model_dump(mode="json")
        if body.slug is not None:
            slug = slugify(body.slug)
            await self._ensure_unique_slug(session, ctx.user_id, slug, exclude_id=skill.id)
            skill.slug = slug
        elif body.name is not None and body.slug is None:
            slug = slugify(body.name)
            if slug != skill.slug:
                await self._ensure_unique_slug(session, ctx.user_id, slug, exclude_id=skill.id)
                skill.slug = slug

        skill.updated_at = datetime.now(UTC)
        session.add(skill)
        await session.commit()
        await session.refresh(skill)
        return await self.get_skill(session, ctx, skill_id)

    async def delete_skill(
        self,
        session: AsyncSession,
        ctx: UserAccessContext,
        skill_id: str,
    ) -> DeleteSkillResponse:
        skill = await self._get_for_manage(session, ctx, skill_id)
        await session.delete(skill)
        await session.commit()
        logger.info("agent_skill_deleted id=%s owner=%s", skill_id, ctx.user_id)
        return DeleteSkillResponse(id=skill_id)


skills_service = SkillsService()
