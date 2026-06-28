"""Postgres model for user-configurable agent skills."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.utils.datetime import datetime, now_utc


class AgentSkill(SQLModel, table=True):
    __tablename__ = "agent_skills"
    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="uq_agent_skill_owner_slug"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    slug: str = Field(max_length=80, nullable=False)
    name: str = Field(max_length=120, nullable=False)
    description: str = Field(default="", max_length=2000, nullable=False)
    content: str = Field(sa_column=Column(Text, nullable=False))
    enabled: bool = Field(default=True, nullable=False)
    access: dict[str, Any] = Field(
        default_factory=lambda: {
            "visibility": "private",
            "allowed_group_ids": [],
            "allowed_roles": [],
        },
        sa_column=Column(JSONB, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)
