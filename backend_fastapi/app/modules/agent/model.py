"""Agent registry models."""

from __future__ import annotations

import enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.utils.datetime import datetime, now_utc


class AgentType(str, enum.Enum):
    NL2SQL = "nl2sql_agent"
    RAG = "rag_agent"
    WEB_SEARCH = "web_search_agent"


class Agent(SQLModel, table=True):
    __tablename__ = "agents"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    type: AgentType = Field(nullable=False)
    description: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
