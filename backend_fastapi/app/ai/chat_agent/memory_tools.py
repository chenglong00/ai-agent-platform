"""Tools for long-term user memory."""

from __future__ import annotations

import logging
from uuid import UUID

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.ai.chat_agent.run_context import get_run_configurable, get_user_id_from_run
from app.core.db.postgres import get_async_session_factory
from app.modules.memory.model import MemorySource
from app.modules.memory.service import memory_service, parse_memory_category

logger = logging.getLogger(__name__)


def _conversation_id_from_run(runtime: ToolRuntime) -> UUID | None:
    thread_id = get_run_configurable(runtime).get("thread_id")
    if not thread_id:
        return None
    try:
        return UUID(str(thread_id))
    except ValueError:
        return None


@tool
async def save_user_memory(
    category: str,
    content: str,
    runtime: ToolRuntime,
) -> str:
    """Save a durable fact, preference, or profile detail about the current user.

    Categories: fact, preference, profile, goal, other.
    Use when the user shares stable information worth remembering across chats.
    """
    cleaned = content.strip()
    if not cleaned:
        return "Memory content cannot be empty."

    try:
        user_id = UUID(get_user_id_from_run(runtime))
        parsed_category = parse_memory_category(category)
        factory = get_async_session_factory()
        async with factory() as session:
            saved = await memory_service.upsert_memory(
                session,
                user_id,
                category=parsed_category,
                content=cleaned,
                source=MemorySource.AGENT,
                conversation_id=_conversation_id_from_run(runtime),
            )
        return f"Saved memory ({saved.category.value}): {saved.content}"
    except Exception as exc:
        logger.exception("save_user_memory_failed")
        return f"Could not save memory: {exc}"


@tool
async def search_user_memories(query: str, runtime: ToolRuntime) -> str:
    """Search this user's long-term memory by keyword or category."""
    try:
        user_id = UUID(get_user_id_from_run(runtime))
        factory = get_async_session_factory()
        async with factory() as session:
            rows = await memory_service.search_for_user(session, user_id, query, limit=15)
        if not rows:
            return "No matching memories found."
        lines = [f"- ({row.category.value}) {row.content}" for row in rows]
        return "Matching memories:\n" + "\n".join(lines)
    except Exception as exc:
        logger.exception("search_user_memories_failed")
        return f"Could not search memory: {exc}"


@tool
async def list_user_memories(runtime: ToolRuntime) -> str:
    """List all stored long-term memories for the current user."""
    try:
        user_id = UUID(get_user_id_from_run(runtime))
        factory = get_async_session_factory()
        async with factory() as session:
            rows = await memory_service.list_for_user(session, user_id, limit=30)
        if not rows:
            return "No memories stored yet for this user."
        lines = [f"- ({row.category.value}) {row.content}" for row in rows]
        return "Stored memories:\n" + "\n".join(lines)
    except Exception as exc:
        logger.exception("list_user_memories_failed")
        return f"Could not list memories: {exc}"
