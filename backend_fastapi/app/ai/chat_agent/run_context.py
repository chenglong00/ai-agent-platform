"""Resolve LangGraph run config from ToolRuntime or async context."""

from __future__ import annotations

from typing import Any

from langgraph.config import get_config


def get_run_configurable(runtime: Any | None = None) -> dict[str, Any]:
    """Return config['configurable'] for the current agent run.

    Deep Agents passes ``ToolRuntime`` (has ``config``) to tools, but
    ``FilesystemMiddleware`` passes bare ``Runtime`` (no ``config``) to backend
    factories during model calls — use ``get_config()`` as fallback.
    """
    config: dict[str, Any] | None = None
    if runtime is not None:
        raw = getattr(runtime, "config", None)
        if isinstance(raw, dict):
            config = raw

    if config is None:
        try:
            config = get_config()
        except RuntimeError:
            config = {}

    if not isinstance(config, dict):
        return {}

    configurable = config.get("configurable")
    return configurable if isinstance(configurable, dict) else {}


def get_user_id_from_run(runtime: Any | None = None) -> str:
    """Return user_id from the current run config, or raise if missing."""
    user_id = get_run_configurable(runtime).get("user_id")
    if not user_id:
        msg = "user_id is required in runnable config['configurable'] for per-user routing"
        raise ValueError(msg)
    return str(user_id)
