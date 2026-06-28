"""Memory API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.memory.model import MemoryCategory, MemorySource


class MemorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: MemoryCategory
    content: str
    source: MemorySource
    conversation_id: UUID | None
    created_at: datetime
    updated_at: datetime


class CreateMemoryRequest(BaseModel):
    category: MemoryCategory = MemoryCategory.FACT
    content: str = Field(..., min_length=1, max_length=4000)


class UpdateMemoryRequest(BaseModel):
    category: MemoryCategory | None = None
    content: str | None = Field(default=None, min_length=1, max_length=4000)


class DeleteMemoryResponse(BaseModel):
    id: UUID
    deleted: bool = True
