"""Per-user Deep Agent sandbox backend pool (local, Modal, Daytona)."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import BackendProtocol

from app.ai.chat_agent.run_context import get_user_id_from_run
from app.ai.chat_agent.playwright_pool import cleanup_idle_browsers
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class _UserSandboxEntry:
    backend: BackendProtocol
    raw_sandbox: Any | None
    last_used_at: float


_cleanup_task: asyncio.Task[None] | None = None
_pool: dict[str, _UserSandboxEntry] = {}
_pool_lock = threading.Lock()


def _backend_name() -> str:
    return settings.DEEP_AGENT_BACKEND.strip().lower()


def _apply_sandbox_env() -> None:
    if settings.DAYTONA_API_KEY:
        os.environ.setdefault("DAYTONA_API_KEY", settings.DAYTONA_API_KEY)
    if settings.DAYTONA_TARGET:
        os.environ.setdefault("DAYTONA_TARGET", settings.DAYTONA_TARGET)
    if settings.DAYTONA_API_URL:
        os.environ.setdefault("DAYTONA_API_URL", settings.DAYTONA_API_URL)
    if settings.MODAL_TOKEN_ID:
        os.environ.setdefault("MODAL_TOKEN_ID", settings.MODAL_TOKEN_ID)
    if settings.MODAL_TOKEN_SECRET:
        os.environ.setdefault("MODAL_TOKEN_SECRET", settings.MODAL_TOKEN_SECRET)


def _destroy_raw_sandbox(raw_sandbox: Any) -> None:
    backend_name = _backend_name()
    try:
        if backend_name == "daytona":
            if hasattr(raw_sandbox, "delete"):
                raw_sandbox.delete()
            elif hasattr(raw_sandbox, "stop"):
                raw_sandbox.stop()
        elif backend_name == "modal" and hasattr(raw_sandbox, "terminate"):
            raw_sandbox.terminate()
    except Exception:
        logger.exception("user_sandbox_shutdown_failed backend=%s", backend_name)


def _create_backend_for_user(user_id: str) -> _UserSandboxEntry:
    backend_name = _backend_name()
    workdir = settings.DEEP_AGENT_SANDBOX_WORKDIR

    if backend_name == "local":
        root_dir = settings.DEEP_AGENT_SANDBOX_LOCAL_ROOT / user_id
        root_dir.mkdir(parents=True, exist_ok=True)
        logger.info("deep_agent_backend=local user_id=%s root_dir=%s", user_id, root_dir)
        return _UserSandboxEntry(
            backend=LocalShellBackend(root_dir=str(root_dir)),
            raw_sandbox=None,
            last_used_at=time.monotonic(),
        )

    _apply_sandbox_env()

    if backend_name == "daytona":
        from daytona import Daytona
        from langchain_daytona import DaytonaSandbox

        raw_sandbox = Daytona().create()
        logger.info(
            "deep_agent_backend=daytona user_id=%s sandbox_id=%s workdir=%s",
            user_id,
            getattr(raw_sandbox, "id", raw_sandbox),
            workdir,
        )
        return _UserSandboxEntry(
            backend=DaytonaSandbox(sandbox=raw_sandbox),
            raw_sandbox=raw_sandbox,
            last_used_at=time.monotonic(),
        )

    if backend_name == "modal":
        import modal
        from langchain_modal import ModalSandbox

        app = modal.App.lookup(settings.DEEP_AGENT_MODAL_APP, create_if_missing=True)
        raw_sandbox = modal.Sandbox.create(app=app, workdir=workdir)
        logger.info(
            "deep_agent_backend=modal user_id=%s app=%s workdir=%s",
            user_id,
            settings.DEEP_AGENT_MODAL_APP,
            workdir,
        )
        return _UserSandboxEntry(
            backend=ModalSandbox(sandbox=raw_sandbox),
            raw_sandbox=raw_sandbox,
            last_used_at=time.monotonic(),
        )

    raise ValueError(
        f"Unsupported DEEP_AGENT_BACKEND={settings.DEEP_AGENT_BACKEND!r}. "
        "Expected one of: local, daytona, modal."
    )


def get_user_backend(user_id: str) -> BackendProtocol:
    """Return the sandbox backend for a user, creating one if needed."""
    key = str(user_id)
    with _pool_lock:
        entry = _pool.get(key)
        if entry is not None:
            entry.last_used_at = time.monotonic()
            return entry.backend

    created = _create_backend_for_user(key)
    with _pool_lock:
        existing = _pool.get(key)
        if existing is not None:
            if created.raw_sandbox is not None:
                _destroy_raw_sandbox(created.raw_sandbox)
            existing.last_used_at = time.monotonic()
            return existing.backend
        _pool[key] = created
        return created.backend


def release_user_sandbox(user_id: str) -> None:
    """Stop and remove a user's sandbox from the pool."""
    key = str(user_id)
    with _pool_lock:
        entry = _pool.pop(key, None)
    if entry is None:
        return
    if entry.raw_sandbox is not None:
        _destroy_raw_sandbox(entry.raw_sandbox)
    logger.info("user_sandbox_released user_id=%s", key)


def shutdown_all_sandboxes() -> None:
    """Stop every pooled sandbox (app shutdown or agent reset)."""
    with _pool_lock:
        entries = list(_pool.items())
        _pool.clear()
    for user_id, entry in entries:
        if entry.raw_sandbox is not None:
            _destroy_raw_sandbox(entry.raw_sandbox)
        logger.info("user_sandbox_shutdown user_id=%s", user_id)


def cleanup_idle_sandboxes() -> int:
    """Release sandboxes idle longer than the configured TTL. Returns count removed."""
    ttl = settings.DEEP_AGENT_SANDBOX_IDLE_TTL_SECONDS
    if ttl <= 0:
        return 0

    now = time.monotonic()
    expired: list[str] = []
    with _pool_lock:
        for user_id, entry in _pool.items():
            if now - entry.last_used_at > ttl:
                expired.append(user_id)

    for user_id in expired:
        release_user_sandbox(user_id)
        logger.info("user_sandbox_idle_expired user_id=%s ttl_s=%s", user_id, ttl)
    return len(expired)


def backend_for_runtime(runtime: Any) -> BackendProtocol:
    """Resolve the per-user backend for a Deep Agents tool or middleware call."""
    return get_user_backend(get_user_id_from_run(runtime))


async def _cleanup_loop() -> None:
    interval = max(settings.DEEP_AGENT_SANDBOX_CLEANUP_INTERVAL_SECONDS, 1)
    while True:
        await asyncio.sleep(interval)
        try:
            removed = await asyncio.to_thread(cleanup_idle_sandboxes)
            if removed:
                logger.info("sandbox_idle_cleanup removed=%s", removed)
            removed_browsers = await cleanup_idle_browsers()
            if removed_browsers:
                logger.info("browser_idle_cleanup removed=%s", removed_browsers)
        except Exception:
            logger.exception("idle_resource_cleanup_failed")


def start_sandbox_cleanup_loop() -> None:
    """Start the background idle-sandbox cleanup task."""
    global _cleanup_task
    if (
        settings.DEEP_AGENT_SANDBOX_IDLE_TTL_SECONDS <= 0
        and settings.BROWSER_PLAYWRIGHT_IDLE_TTL_SECONDS <= 0
    ):
        return
    if _cleanup_task is not None and not _cleanup_task.done():
        return
    _cleanup_task = asyncio.create_task(_cleanup_loop())
    logger.info(
        "sandbox_cleanup_loop_started ttl_s=%s interval_s=%s",
        settings.DEEP_AGENT_SANDBOX_IDLE_TTL_SECONDS,
        settings.DEEP_AGENT_SANDBOX_CLEANUP_INTERVAL_SECONDS,
    )


async def stop_sandbox_cleanup_loop() -> None:
    """Cancel the background idle-sandbox cleanup task."""
    global _cleanup_task
    task = _cleanup_task
    _cleanup_task = None
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
