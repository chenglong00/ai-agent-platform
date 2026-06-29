"""Per-user A2A subagent registrations."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.utils.datetime import datetime, now_utc


class UserSubagent(SQLModel, table=True):
    __tablename__ = "user_subagents"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_url", name="uq_user_subagent_url"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    name: str = Field(max_length=200, nullable=False)
    description: str = Field(default="", max_length=4000, nullable=False)
    agent_url: str = Field(max_length=2048, nullable=False)
    agent_card: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
    )
    enabled: bool = Field(default=True, nullable=False)
    last_verified_at: datetime | None = Field(default=None, nullable=True)
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)
