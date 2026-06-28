from __future__ import annotations

import enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import relationship
from sqlmodel import SQLModel, Field, Relationship

from app.utils.datetime import now_utc, datetime


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    email: str = Field(index=True, unique=True, nullable=False, max_length=320)

    display_name: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=2048)

    role: UserRole = Field(default=UserRole.MEMBER, nullable=False)
    is_approved: bool = Field(default=False, nullable=False)
    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)

    identities: list["AuthIdentity"] = Relationship(
        sa_relationship=relationship(
            "AuthIdentity",
            back_populates="user",
            cascade="all, delete-orphan",
        ),
    )
    conversations: list["Conversation"] = Relationship(
        sa_relationship=relationship(
            "Conversation",
            back_populates="owner",
            cascade="all, delete-orphan",
        ),
    )
    group_memberships: list["GroupMember"] = Relationship(
        sa_relationship=relationship(
            "GroupMember",
            back_populates="user",
            cascade="all, delete-orphan",
        ),
    )
