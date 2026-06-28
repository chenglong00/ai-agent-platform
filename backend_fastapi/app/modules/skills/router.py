"""Agent skills API."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.ai.skills.loader import discover_skills, read_builtin_skill_body
from app.core.security.dependencies import get_db
from app.modules.auth.rbac import RequireUser
from app.modules.group.model import GroupMember, UserGroup
from app.modules.knowledge_base.access import build_user_access_context
from app.modules.knowledge_base.schema import GroupOption
from app.modules.skills.schema import (
    CreateSkillRequest,
    DeleteSkillResponse,
    SkillAccessControl,
    SkillDetail,
    SkillOptionsResponse,
    SkillSummary,
    UpdateSkillRequest,
)
from app.modules.skills.service import skills_service
from app.modules.user.schema import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()


async def _user_groups(session: AsyncSession, user: UserResponse) -> list[GroupOption]:
    statement = (
        select(UserGroup)
        .join(GroupMember, GroupMember.group_id == UserGroup.id)
        .where(GroupMember.user_id == user.id)
        .order_by(UserGroup.name.asc())
    )
    result = await session.exec(statement)
    return [GroupOption(id=g.id, name=g.name) for g in result.all()]


@router.get("/options", response_model=SkillOptionsResponse)
async def get_options(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> SkillOptionsResponse:
    groups = await _user_groups(session, current_user)
    return skills_service.options(groups=groups)


@router.get("/builtins", response_model=list[SkillSummary])
async def list_builtin_skills(
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> list[SkillSummary]:
    _ = current_user
    return [
        SkillSummary(
            id=skill.id,
            slug=skill.id,
            name=skill.name,
            description=skill.description,
            source="builtin",
            enabled=True,
            access=SkillAccessControl(visibility="organization"),
            is_owner=False,
        )
        for skill in discover_skills()
    ]


@router.get("/builtins/{slug}", response_model=SkillDetail)
async def get_builtin_skill(
    slug: str,
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> SkillDetail:
    _ = current_user
    try:
        name, description, content = read_builtin_skill_body(slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Skill not found") from exc
    return SkillDetail(
        id=slug,
        slug=slug,
        name=name,
        description=description,
        source="builtin",
        enabled=True,
        access=SkillAccessControl(visibility="organization"),
        is_owner=False,
        content=content,
        can_manage=False,
    )


@router.get("", response_model=list[SkillSummary])
async def list_skills(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> list[SkillSummary]:
    ctx = await build_user_access_context(session, current_user)
    return await skills_service.list_skills(session, ctx)


@router.post("", response_model=SkillDetail)
async def create_skill(
    body: CreateSkillRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> SkillDetail:
    ctx = await build_user_access_context(session, current_user)
    return await skills_service.create_skill(session, ctx, body)


@router.get("/{skill_id}", response_model=SkillDetail)
async def get_skill(
    skill_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> SkillDetail:
    ctx = await build_user_access_context(session, current_user)
    return await skills_service.get_skill(session, ctx, skill_id)


@router.patch("/{skill_id}", response_model=SkillDetail)
async def update_skill(
    skill_id: str,
    body: UpdateSkillRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> SkillDetail:
    ctx = await build_user_access_context(session, current_user)
    return await skills_service.update_skill(session, ctx, skill_id, body)


@router.delete("/{skill_id}", response_model=DeleteSkillResponse)
async def delete_skill(
    skill_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> DeleteSkillResponse:
    ctx = await build_user_access_context(session, current_user)
    return await skills_service.delete_skill(session, ctx, skill_id)
