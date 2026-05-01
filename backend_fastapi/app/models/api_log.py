from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Column, Field, JSON, SQLModel

from app.models.user import User  # noqa: F401 - ensure users table in metadata before api_logs FK


class ApiLog(SQLModel, table=True):
    """One row per API request. Identify caller by api_key (key auth) and/or user_id (user auth)."""

    __tablename__ = "api_logs"
    __table_args__ = (Index("ix_api_logs_user_id", "user_id"), Index("ix_api_logs_created_at", "created_at"))

    id: int | None = Field(default=None, primary_key=True)
    correlation_id: str | None = Field(default=None, index=True, max_length=64)  # X-Request-ID, link to app logs
    api_key: uuid.UUID | None = Field(default=None)  # set when request authenticated via API key
    user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")  # set when request authenticated as user
    ip_address: str = Field(max_length=45)
    path: str = Field(max_length=2048)
    method: str = Field(max_length=16)
    status_code: int
    request_body: dict | list | None = Field(default=None, sa_column=Column(JSON))
    response_body: dict | list | None = Field(default=None, sa_column=Column(JSON))
    query_params: dict | None = Field(default=None, sa_column=Column(JSON))
    path_params: dict | None = Field(default=None, sa_column=Column(JSON))
    process_time_ms: float  # milliseconds
    created_at: datetime

    class Config:
        allow_arbitrary_types = True