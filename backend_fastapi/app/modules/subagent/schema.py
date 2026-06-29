"""Subagent API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SubagentSkillSummary(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)


class SubagentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    agent_url: str
    enabled: bool
    agent_version: str | None = None
    streaming: bool = False
    skills: list[SubagentSkillSummary] = Field(default_factory=list)
    last_verified_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class RegisterSubagentRequest(BaseModel):
    agent_url: HttpUrl
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class UpdateSubagentRequest(BaseModel):
    enabled: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class DeleteSubagentResponse(BaseModel):
    id: UUID
    deleted: bool = True


class RefreshSubagentResponse(BaseModel):
    subagent: SubagentSummary
