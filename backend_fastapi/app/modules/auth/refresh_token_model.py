"""Server-side refresh tokens for session rotation and revocation."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from app.utils.datetime import datetime, now_utc


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    token_hash: str = Field(max_length=64, nullable=False, unique=True, index=True)
    expires_at: datetime = Field(nullable=False)
    revoked_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
