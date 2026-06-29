"""Langfuse tracing for LangChain / LangGraph agent runs."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)

_TRACE_INPUT_MAX_CHARS = 2000
_TRACE_OUTPUT_MAX_CHARS = 4000

_initialized = False


def is_langfuse_enabled() -> bool:
    return bool(
        settings.LANGFUSE_PUBLIC_KEY.strip()
        and settings.LANGFUSE_SECRET_KEY.strip()
        and settings.LANGFUSE_BASE_URL.strip()
    )


def _sync_langfuse_env() -> None:
    """Ensure the Langfuse SDK reads credentials from pydantic-loaded settings."""
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    base_url = settings.LANGFUSE_BASE_URL.rstrip("/")
    os.environ["LANGFUSE_BASE_URL"] = base_url
    os.environ["LANGFUSE_HOST"] = base_url


def init_langfuse() -> None:
    """Initialize the Langfuse client once at startup."""
    global _initialized
    if not is_langfuse_enabled() or _initialized:
        return
    _sync_langfuse_env()
    try:
        from langfuse import get_client

        get_client()
        _initialized = True
        logger.info("langfuse_initialized base_url=%s", settings.LANGFUSE_BASE_URL)
    except Exception:
        logger.exception("langfuse_init_failed")


def flush_langfuse() -> None:
    """Flush pending Langfuse events before shutdown."""
    if not is_langfuse_enabled() or not _initialized:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        logger.exception("langfuse_flush_failed")


def _truncate(text: str, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3] + "..."


def record_trace_io(*, user_input: str, assistant_output: str) -> None:
    """Set readable trace-level input/output (user message + assistant reply only)."""
    if not is_langfuse_enabled():
        return
    try:
        from langfuse import get_client

        get_client().set_current_trace_io(
            input={"message": _truncate(user_input, _TRACE_INPUT_MAX_CHARS)},
            output={"message": _truncate(assistant_output, _TRACE_OUTPUT_MAX_CHARS)},
        )
    except Exception:
        logger.exception("langfuse_record_trace_io_failed")


@contextmanager
def agent_trace_context(
    *,
    trace_name: str,
    user_id: UUID,
    session_id: str | None,
    user_text: str,
    streaming: bool = False,
    tags: list[str] | None = None,
) -> Iterator[Any | None]:
    """Yield a LangChain CallbackHandler inside a Langfuse trace context, or None if disabled."""
    if not is_langfuse_enabled():
        yield None
        return

    init_langfuse()
    from langfuse import propagate_attributes
    from langfuse.langchain import CallbackHandler

    trace_tags = list(tags or [])
    trace_tags.append("streaming" if streaming else "sync")

    with propagate_attributes(
        trace_name=trace_name,
        user_id=str(user_id),
        session_id=session_id,
        tags=trace_tags,
        metadata={"user_message_chars": str(len(user_text.strip()))},
    ):
        yield CallbackHandler()
