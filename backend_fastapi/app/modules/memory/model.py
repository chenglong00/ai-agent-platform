"""Long-term user memory stored in Postgres."""

from __future__ import annotations

import enum
from uuid import UUID, uuid4

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.utils.datetime import datetime, now_utc


class MemoryCategory(str, enum.Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    PROFILE = "profile"
    GOAL = "goal"
    OTHER = "other"


class MemorySource(str, enum.Enum):
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


class UserMemory(SQLModel, table=True):
    __tablename__ = "user_memories"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    category: MemoryCategory = Field(nullable=False, index=True)
    content: str = Field(sa_column=Column(Text, nullable=False))
    source: MemorySource = Field(default=MemorySource.AGENT, nullable=False)
    conversation_id: UUID | None = Field(default=None, nullable=True, index=True)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)
