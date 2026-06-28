"""Model definitions for user groups/teams and membership management.
"""

from __future__ import annotations

import enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint
from app.utils.datetime import now_utc, datetime
from app.modules.user.model import User


class GroupRole(str, enum.Enum):
    OWNER = "GROUP_OWNER"
    ADMIN = "GROUP_ADMIN"
    MEMBER = "GROUP_MEMBER"


class UserGroup(SQLModel, table=True):
    __tablename__ = "user_groups"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True, unique=True, nullable=False, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    
    # Global group owner (maps to a User ID)
    owner_id: UUID = Field(nullable=False) # Foreign Key to users.id

    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)

    members: list["GroupMember"] = Relationship(
        sa_relationship=relationship(
            "GroupMember",
            back_populates="group",
            cascade="all, delete-orphan",
        ),
    )


class GroupMember(SQLModel, table=True):
    __tablename__ = "group_members"

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_user"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: UUID = Field(foreign_key="user_groups.id", nullable=False)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    
    role: GroupRole = Field(default=GroupRole.MEMBER, nullable=False)
    
    joined_at: datetime = Field(default_factory=now_utc, nullable=False)

    group: UserGroup = Relationship(back_populates="members")
    user: Optional["User"] = Relationship(
        sa_relationship=relationship("User", back_populates="group_memberships"),
    )
