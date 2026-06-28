"""Access control helpers for agent skills."""

from __future__ import annotations

from typing import Any

from app.modules.knowledge_base.access import (
    UserAccessContext,
    can_manage,
    can_read,
    parse_access,
)
from app.modules.skills.model import AgentSkill


def skill_as_doc(skill: AgentSkill) -> dict[str, Any]:
    return {
        "owner_id": str(skill.owner_id),
        "access": skill.access,
        "enabled": skill.enabled,
        "name": skill.name,
        "description": skill.description,
        "content": skill.content,
    }


def can_read_skill(ctx: UserAccessContext, skill: AgentSkill) -> bool:
    return can_read(ctx, skill_as_doc(skill))


def can_manage_skill(ctx: UserAccessContext, skill: AgentSkill) -> bool:
    return can_manage(ctx, skill_as_doc(skill))


def parse_skill_access(skill: AgentSkill):
    return parse_access(skill_as_doc(skill))
