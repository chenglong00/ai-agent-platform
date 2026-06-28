"""Tools for loading agent skills."""

from __future__ import annotations

import logging

from fastapi import HTTPException
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.ai.chat_agent.run_context import get_user_access_context_from_run
from app.ai.skills.loader import discover_skills, read_skill_markdown
from app.core.db.postgres import get_async_session_factory
from app.modules.skills.service import skills_service

logger = logging.getLogger(__name__)


def _format_builtin_skills() -> list[str]:
    lines: list[str] = []
    for skill in discover_skills():
        lines.append(f"- {skill.id} (builtin): {skill.description}")
    return lines


@tool
async def list_skills(runtime: ToolRuntime) -> str:
    """List skills available to the current user. Call before read_skill for specialized workflows."""
    lines = _format_builtin_skills()
    try:
        ctx = get_user_access_context_from_run(runtime)
        factory = get_async_session_factory()
        async with factory() as session:
            custom = await skills_service.list_skills(session, ctx)
        for skill in custom:
            if not skill.enabled:
                continue
            owner = " (yours)" if skill.is_owner else ""
            lines.append(f"- {skill.id}{owner}: {skill.description or skill.name}")
    except (RuntimeError, ValueError) as exc:
        if not lines:
            return f"No skills available. ({exc})"
        lines.append(f"(Custom skills unavailable: {exc})")
    if not lines:
        return "No skills are configured yet."
    return "Available skills:\n" + "\n".join(lines)


@tool
async def read_skill(skill_id: str, runtime: ToolRuntime) -> str:
    """Load full skill instructions by id. Use list_skills first to see available ids."""
    normalized = skill_id.strip()
    if not normalized:
        return "Provide a skill id from list_skills."

    try:
        return read_skill_markdown(normalized)
    except ValueError:
        pass

    try:
        ctx = get_user_access_context_from_run(runtime)
        factory = get_async_session_factory()
        async with factory() as session:
            return await skills_service.read_skill_content(session, ctx, normalized)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return f"Could not load skill '{normalized}': {detail}"
    except Exception as exc:
        logger.exception("read_skill_failed id=%s", normalized)
        available = ", ".join(s.id for s in discover_skills()) or "(none)"
        return f"Could not load skill '{normalized}': {exc}. Built-in skills: {available}"
