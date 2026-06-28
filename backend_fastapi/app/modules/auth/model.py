from __future__ import annotations

import enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlmodel import SQLModel, Field, Relationship

from app.core.crypto import EncryptedString
from app.utils.datetime import now_utc, datetime


class AuthProvider(str, enum.Enum):
    google = "google"
    github = "github"
    microsoft = "microsoft"
    credentials = "credentials"


class AuthIdentity(SQLModel, table=True):
    __tablename__ = "auth_identities"

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_account"),
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
        Index("ix_auth_identities_user_id", "user_id"),
        Index("ix_auth_identities_provider_user_id", "provider_user_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False)

    provider: AuthProvider = Field(nullable=False)

    provider_user_id: Optional[str] = Field(default=None, max_length=255)

    password_hash: Optional[str] = Field(default=None, max_length=255)
    password_algo: Optional[str] = Field(default=None, max_length=32)
    password_updated_at: Optional[datetime] = Field(default=None)

    email_verified: Optional[bool] = Field(default=None)
    last_login_at: Optional[datetime] = Field(default=None)

    access_token: Optional[str] = Field(default=None, sa_column=Column(EncryptedString(), nullable=True))
    refresh_token: Optional[str] = Field(default=None, sa_column=Column(EncryptedString(), nullable=True))
    token_expires_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)

    user: Optional["User"] = Relationship(
        sa_relationship=relationship("User", back_populates="identities"),
    )
