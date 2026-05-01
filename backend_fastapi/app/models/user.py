from __future__ import annotations

import enum

from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlmodel import SQLModel, Field, Relationship
from app.utils.datetime import now_utc, datetime
from app.core.crypto import EncryptedString

class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class AuthProvider(str, enum.Enum):
    google = "google"
    github = "github"
    microsoft = "microsoft"
    credentials = "credentials"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # One email per user (normalize to lowercase in app code!)
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


class AuthIdentity(SQLModel, table=True):
    __tablename__ = "auth_identities"

    __table_args__ = (
        # Prevent the same Google/Microsoft account being linked to multiple users
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_account"),
        # One identity per provider per user (good default)
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
        Index("ix_auth_identities_user_id", "user_id"),
        Index("ix_auth_identities_provider_user_id", "provider_user_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False)

    provider: AuthProvider = Field(nullable=False)

    # OAuth: required for google/microsoft; NULL for credentials
    provider_user_id: Optional[str] = Field(default=None, max_length=255)

    # Credentials-only
    password_hash: Optional[str] = Field(default=None, max_length=255)
    password_algo: Optional[str] = Field(default=None, max_length=32)
    password_updated_at: Optional[datetime] = Field(default=None)

    email_verified: Optional[bool] = Field(default=None)
    last_login_at: Optional[datetime] = Field(default=None)

    # OAuth: store tokens to call provider APIs (e.g. Gmail, Drive). NULL for credentials. Never expose in API responses.
    # Stored encrypted at rest when ENCRYPTION_KEY is set.
    access_token: Optional[str] = Field(default=None, sa_column=Column(EncryptedString(), nullable=True))
    refresh_token: Optional[str] = Field(default=None, sa_column=Column(EncryptedString(), nullable=True))
    token_expires_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)

    user: Optional[User] = Relationship(
        sa_relationship=relationship("User", back_populates="identities"),
    )
