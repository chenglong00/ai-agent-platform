"""A2A subagent registry API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security.dependencies import get_db
from app.modules.auth.rbac import RequireUser
from app.modules.subagent.schema import (
    DeleteSubagentResponse,
    RefreshSubagentResponse,
    RegisterSubagentRequest,
    SubagentSummary,
    UpdateSubagentRequest,
)
from app.modules.subagent.service import subagent_service
from app.modules.user.schema import UserResponse

router = APIRouter()


@router.get("", response_model=list[SubagentSummary])
async def list_subagents(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> list[SubagentSummary]:
    return await subagent_service.list_for_user(session, current_user.id)


@router.post("/register", response_model=SubagentSummary)
async def register_subagent(
    body: RegisterSubagentRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> SubagentSummary:
    return await subagent_service.register(session, current_user.id, body)


@router.post("/{subagent_id}/refresh", response_model=RefreshSubagentResponse)
async def refresh_subagent(
    subagent_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> RefreshSubagentResponse:
    subagent = await subagent_service.refresh(session, current_user.id, subagent_id)
    return RefreshSubagentResponse(subagent=subagent)


@router.patch("/{subagent_id}", response_model=SubagentSummary)
async def update_subagent(
    subagent_id: UUID,
    body: UpdateSubagentRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> SubagentSummary:
    return await subagent_service.update(session, current_user.id, subagent_id, body)


@router.delete("/{subagent_id}", response_model=DeleteSubagentResponse)
async def delete_subagent(
    subagent_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> DeleteSubagentResponse:
    await subagent_service.delete(session, current_user.id, subagent_id)
    return DeleteSubagentResponse(id=subagent_id)
