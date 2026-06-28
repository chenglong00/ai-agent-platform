"""User long-term memory API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security.dependencies import get_db
from app.modules.auth.rbac import RequireUser
from app.modules.memory.schema import (
    CreateMemoryRequest,
    DeleteMemoryResponse,
    MemorySummary,
    UpdateMemoryRequest,
)
from app.modules.memory.service import memory_service
from app.modules.user.schema import UserResponse

router = APIRouter()


@router.get("", response_model=list[MemorySummary])
async def list_memories(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> list[MemorySummary]:
    return await memory_service.list_for_user(session, current_user.id)


@router.post("", response_model=MemorySummary)
async def create_memory(
    body: CreateMemoryRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> MemorySummary:
    return await memory_service.create_memory(session, current_user.id, body)


@router.patch("/{memory_id}", response_model=MemorySummary)
async def update_memory(
    memory_id: UUID,
    body: UpdateMemoryRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> MemorySummary:
    return await memory_service.update_memory(session, current_user.id, memory_id, body)


@router.delete("/{memory_id}", response_model=DeleteMemoryResponse)
async def delete_memory(
    memory_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> DeleteMemoryResponse:
    await memory_service.delete_memory(session, current_user.id, memory_id)
    return DeleteMemoryResponse(id=memory_id)
