"""Per-user enterprise connector credentials."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.security.crypto import EncryptedString
from app.utils.datetime import datetime, now_utc


class UserConnector(SQLModel, table=True):
    __tablename__ = "user_connectors"

    __table_args__ = (
        UniqueConstraint("user_id", "connector_id", name="uq_user_connector"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    connector_id: str = Field(max_length=64, nullable=False, index=True)
    enabled: bool = Field(default=True, nullable=False)
    account_email: str | None = Field(default=None, max_length=255, nullable=True)
    scopes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    access_token: str | None = Field(default=None, sa_column=Column(EncryptedString(), nullable=True))
    refresh_token: str | None = Field(default=None, sa_column=Column(EncryptedString(), nullable=True))
    token_expires_at: datetime | None = Field(default=None, nullable=True)
    last_connected_at: datetime | None = Field(default=None, nullable=True)
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)
