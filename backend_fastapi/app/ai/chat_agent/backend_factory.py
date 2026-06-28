"""Per-user Deep Agent sandbox backend pool (local, Modal, Daytona).

Daytona uses ONE shared VM. Each user gets:

- home: ``/home/{user_slug}/``
- workspace: ``/home/{user_slug}/workspace/``

``DEEP_AGENT_SANDBOX_HOME_ROOT`` defaults to ``/home``; VM init uses sudo when needed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import BackendProtocol, SandboxBackendProtocol

from app.ai.chat_agent.run_context import get_user_id_from_run
from app.ai.chat_agent.playwright_pool import cleanup_idle_browsers
from app.ai.chat_agent.sandbox_paths import load_sandbox_paths
from app.ai.chat_agent.sandbox_shell import ensure_directory_command
from app.ai.chat_agent.user_scoped_backend import UserScopedSandboxBackend
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class _UserSandboxEntry:
    backend: BackendProtocol
    raw_sandbox: Any | None
    last_used_at: float


@dataclass
class _SharedDaytonaEntry:
    raw_sandbox: Any
    inner_backend: SandboxBackendProtocol


_cleanup_task: asyncio.Task[None] | None = None
_pool: dict[str, _UserSandboxEntry] = {}
_pool_lock = threading.Lock()
_user_create_locks: dict[str, threading.Lock] = {}
_shared_daytona: _SharedDaytonaEntry | None = None
_shared_daytona_lock = threading.Lock()


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


def _destroy_raw_sandbox(raw_sandbox: Any, *, force: bool = False) -> None:
    backend_name = _backend_name()
    if backend_name == "daytona" and not force and not settings.DAYTONA_DELETE_ON_SHUTDOWN:
        logger.info(
            "daytona_sandbox_kept_alive sandbox_id=%s",
            getattr(raw_sandbox, "id", raw_sandbox),
        )
        return
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


def _pick_existing_daytona_sandbox(client: Any) -> Any | None:
    """Reuse a running sandbox when DAYTONA_SANDBOX_ID is unset."""
    try:
        sandboxes = list(client.list())
    except Exception:
        logger.exception("daytona_list_sandboxes_failed")
        return None
    if not sandboxes:
        return None
    for sb in sandboxes:
        state = str(getattr(sb, "state", "") or "").lower()
        if "start" in state or state in {"", "running", "active"}:
            return sb
    return sandboxes[0]


def _home_base_dir() -> str:
    return settings.DEEP_AGENT_SANDBOX_HOME_ROOT.rstrip("/") or "/home"


def _sandbox_state_name(raw_sandbox: Any) -> str:
    state = getattr(raw_sandbox, "state", None)
    if state is None:
        return ""
    value = getattr(state, "value", state)
    return str(value).lower()


def _is_daytona_sandbox_running(raw_sandbox: Any) -> bool:
    return _sandbox_state_name(raw_sandbox) == "started"


def _ensure_daytona_sandbox_started(client: Any, raw_sandbox: Any) -> Any:
    """Start a stopped sandbox and wait until the container has an IP."""
    sandbox_id = str(getattr(raw_sandbox, "id", raw_sandbox))
    state = _sandbox_state_name(raw_sandbox)
    if state == "started":
        return raw_sandbox

    if state in {"error", "destroyed", "destroying", "build_failed"}:
        raise RuntimeError(
            f"Daytona sandbox {sandbox_id} is unavailable (state={state})"
        )

    if state in {"stopped", "paused", "archived"}:
        logger.info("daytona_sandbox_starting sandbox_id=%s state=%s", sandbox_id, state)
        if hasattr(raw_sandbox, "start"):
            raw_sandbox.start()
        else:
            raise RuntimeError(f"Daytona sandbox {sandbox_id} cannot be started (state={state})")
    elif state in {"starting", "restoring", "creating", "resuming", "pulling_snapshot"}:
        logger.info("daytona_sandbox_waiting sandbox_id=%s state=%s", sandbox_id, state)
    else:
        logger.info(
            "daytona_sandbox_waiting sandbox_id=%s state=%s (unexpected)",
            sandbox_id,
            state or "unknown",
        )

    timeout_s = max(settings.DAYTONA_START_TIMEOUT_SECONDS, 10)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        raw_sandbox = client.get(sandbox_id)
        state = _sandbox_state_name(raw_sandbox)
        if state == "started":
            logger.info("daytona_sandbox_ready sandbox_id=%s", sandbox_id)
            return raw_sandbox
        if state in {"error", "destroyed", "destroying", "build_failed"}:
            raise RuntimeError(
                f"Daytona sandbox {sandbox_id} failed to start (state={state})"
            )
        time.sleep(2)

    raise RuntimeError(
        f"Daytona sandbox {sandbox_id} did not start within {timeout_s}s "
        f"(last state={state or 'unknown'})"
    )


def _daytona_create_params() -> Any | None:
    auto_stop = settings.DAYTONA_AUTO_STOP_MINUTES
    if auto_stop <= 0:
        return None
    from daytona import CreateSandboxFromSnapshotParams

    return CreateSandboxFromSnapshotParams(auto_stop_interval=auto_stop)


def _attach_daytona_sandbox(client: Any, raw_sandbox: Any) -> tuple[Any, SandboxBackendProtocol]:
    raw_sandbox = _ensure_daytona_sandbox_started(client, raw_sandbox)
    from langchain_daytona import DaytonaSandbox

    inner = DaytonaSandbox(sandbox=raw_sandbox)
    _prepare_shared_sandbox_dirs(inner)
    return raw_sandbox, inner


def _prepare_shared_sandbox_dirs(inner: SandboxBackendProtocol) -> None:
    """Ensure /home (or configured root) is writable for all sandbox users."""
    base = _home_base_dir()
    inner.execute(ensure_directory_command(base))


def _get_or_create_shared_daytona() -> SandboxBackendProtocol:
    """Return the single shared Daytona backend (creates one VM if needed)."""
    global _shared_daytona
    with _shared_daytona_lock:
        if _shared_daytona is not None:
            return _shared_daytona.inner_backend

        _apply_sandbox_env()
        from daytona import Daytona
        from langchain_daytona import DaytonaSandbox

        client = Daytona()
        sandbox_id = settings.DAYTONA_SANDBOX_ID.strip()
        if sandbox_id:
            raw_sandbox = client.get(sandbox_id)
            logger.info("deep_agent_daytona_reused sandbox_id=%s", sandbox_id)
        else:
            raw_sandbox = _pick_existing_daytona_sandbox(client)
            if raw_sandbox is not None:
                sandbox_id = str(getattr(raw_sandbox, "id", raw_sandbox))
                logger.info(
                    "deep_agent_daytona_reused_existing sandbox_id=%s "
                    "(set DAYTONA_SANDBOX_ID=%s in .env to pin)",
                    sandbox_id,
                    sandbox_id,
                )
            else:
                raw_sandbox = client.create()
                sandbox_id = str(getattr(raw_sandbox, "id", raw_sandbox))
                logger.info(
                    "deep_agent_daytona_created sandbox_id=%s "
                    "— add DAYTONA_SANDBOX_ID=%s to .env.local so files survive restarts",
                    sandbox_id,
                    sandbox_id,
                )

        inner = DaytonaSandbox(sandbox=raw_sandbox)
        _prepare_shared_sandbox_dirs(inner)
        _shared_daytona = _SharedDaytonaEntry(
            raw_sandbox=raw_sandbox,
            inner_backend=inner,
        )
        return inner


def _shutdown_shared_daytona() -> None:
    global _shared_daytona
    with _shared_daytona_lock:
        entry = _shared_daytona
        _shared_daytona = None
    if entry is None:
        return
    _destroy_raw_sandbox(entry.raw_sandbox)
    logger.info(
        "shared_daytona_shutdown sandbox_id=%s",
        getattr(entry.raw_sandbox, "id", entry.raw_sandbox),
    )


def _create_backend_for_user(user_id: str) -> _UserSandboxEntry:
    backend_name = _backend_name()
    paths = load_sandbox_paths(user_id)

    if backend_name == "local":
        from pathlib import Path

        Path(paths.home).mkdir(parents=True, exist_ok=True)
        Path(paths.workspace).mkdir(parents=True, exist_ok=True)
        logger.info(
            "deep_agent_backend=local user_id=%s home=%s workspace=%s",
            user_id,
            paths.home,
            paths.workspace,
        )
        return _UserSandboxEntry(
            backend=LocalShellBackend(root_dir=paths.workspace),
            raw_sandbox=None,
            last_used_at=time.monotonic(),
        )

    _apply_sandbox_env()

    if backend_name == "daytona":
        inner = _get_or_create_shared_daytona()
        scoped = UserScopedSandboxBackend(
            inner,
            user_id=user_id,
            user_root=paths.workspace,
            execute_cwd=paths.workspace,
            home=paths.home,
        )
        scoped.ensure_user_root()
        logger.info(
            "deep_agent_backend=daytona user_id=%s slug=%s home=%s workspace=%s sandbox_id=%s",
            user_id,
            paths.slug,
            paths.home,
            paths.workspace,
            inner.id,
        )
        return _UserSandboxEntry(
            backend=scoped,
            raw_sandbox=None,
            last_used_at=time.monotonic(),
        )

    if backend_name == "modal":
        import modal
        from langchain_modal import ModalSandbox

        app = modal.App.lookup(settings.DEEP_AGENT_MODAL_APP, create_if_missing=True)
        raw_sandbox = modal.Sandbox.create(app=app, workdir=paths.home)
        inner = ModalSandbox(sandbox=raw_sandbox)
        scoped = UserScopedSandboxBackend(
            inner,
            user_id=user_id,
            user_root=paths.workspace,
            execute_cwd=paths.workspace,
            home=paths.home,
        )
        scoped.ensure_user_root()
        logger.info(
            "deep_agent_backend=modal user_id=%s home=%s workspace=%s",
            user_id,
            paths.home,
            paths.workspace,
        )
        return _UserSandboxEntry(
            backend=scoped,
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
        lock = _user_create_locks.setdefault(key, threading.Lock())

    with lock:
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
    """Remove a user's pooled backend handle (does not delete shared Daytona VM)."""
    key = str(user_id)
    with _pool_lock:
        entry = _pool.pop(key, None)
    if entry is None:
        return
    if entry.raw_sandbox is not None:
        _destroy_raw_sandbox(entry.raw_sandbox)
    logger.info("user_sandbox_released user_id=%s", key)


def shutdown_all_sandboxes() -> None:
    """Stop pooled backends and the shared Daytona VM (if any)."""
    with _pool_lock:
        entries = list(_pool.items())
        _pool.clear()
    for user_id, entry in entries:
        if entry.raw_sandbox is not None:
            _destroy_raw_sandbox(entry.raw_sandbox)
        logger.info("user_sandbox_shutdown user_id=%s", user_id)
    if _backend_name() == "daytona":
        _shutdown_shared_daytona()


def cleanup_idle_sandboxes() -> int:
    """Release idle user backend handles. Returns count removed."""
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
