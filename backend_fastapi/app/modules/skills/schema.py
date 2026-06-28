"""Skills API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.modules.knowledge_base.schema import (
    AccessVisibilityOption,
    DocumentAccessControl,
    GroupOption,
    RoleOption,
    Visibility,
)

SkillSource = Literal["builtin", "custom"]


class SkillAccessControl(DocumentAccessControl):
    """Same visibility model as knowledge base documents."""


class SkillOptionsResponse(BaseModel):
    access_visibility_options: list[AccessVisibilityOption]
    role_options: list[RoleOption]
    groups: list[GroupOption] = Field(default_factory=list)


class SkillSummary(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    source: SkillSource
    enabled: bool = True
    access: SkillAccessControl
    is_owner: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SkillDetail(SkillSummary):
    content: str
    can_manage: bool = False


class CreateSkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    content: str = Field(min_length=1, max_length=100_000)
    slug: str | None = Field(default=None, max_length=80)
    enabled: bool = True
    access: SkillAccessControl = Field(default_factory=SkillAccessControl)


class UpdateSkillRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    content: str | None = Field(default=None, min_length=1, max_length=100_000)
    slug: str | None = Field(default=None, max_length=80)
    enabled: bool | None = None
    access: SkillAccessControl | None = None

    @field_validator("name", "description", "content", "slug", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None or not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


class DeleteSkillResponse(BaseModel):
    id: str
    deleted: bool = True
