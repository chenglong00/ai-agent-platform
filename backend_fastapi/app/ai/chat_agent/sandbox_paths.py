"""Per-user sandbox path layout (shared Daytona VM or local dev)."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9_-]+")


@dataclass(frozen=True, slots=True)
class SandboxUserPaths:
    slug: str
    home: str
    workspace: str


def sandbox_user_slug(
    user_id: str,
    *,
    email: str | None = None,
    display_name: str | None = None,
) -> str:
    """Filesystem-safe directory name under the sandbox home root (unique per user id)."""
    raw = (display_name or "").strip()
    if not raw and email:
        raw = email.split("@", 1)[0].strip()
    if not raw:
        raw = "user"
    base = _SLUG_RE.sub("_", raw.lower()).strip("_")[:40] or "user"
    suffix = str(user_id).replace("-", "")[:8]
    return f"{base}_{suffix}"


def remote_sandbox_paths(
    user_id: str,
    *,
    email: str | None = None,
    display_name: str | None = None,
) -> SandboxUserPaths:
    """Paths inside the shared Daytona/Modal VM."""
    slug = sandbox_user_slug(user_id, email=email, display_name=display_name)
    home_root = settings.DEEP_AGENT_SANDBOX_HOME_ROOT.rstrip("/") or "/home"
    workspace_dir = settings.DEEP_AGENT_SANDBOX_WORKSPACE_DIR.strip("/") or "workspace"
    home = f"{home_root}/{slug}"
    return SandboxUserPaths(slug=slug, home=home, workspace=f"{home}/{workspace_dir}")


def local_sandbox_paths(user_id: str) -> SandboxUserPaths:
    """Paths on the host when DEEP_AGENT_BACKEND=local."""
    safe_id = str(user_id).replace("/", "_")
    home = (settings.DEEP_AGENT_SANDBOX_LOCAL_ROOT / safe_id).resolve()
    workspace_dir = settings.DEEP_AGENT_SANDBOX_WORKSPACE_DIR.strip("/") or "workspace"
    return SandboxUserPaths(
        slug=safe_id,
        home=str(home),
        workspace=str(home / workspace_dir),
    )


def resolve_sandbox_paths(
    user_id: str,
    *,
    email: str | None = None,
    display_name: str | None = None,
) -> SandboxUserPaths:
    backend = settings.DEEP_AGENT_BACKEND.strip().lower()
    if backend == "local":
        return local_sandbox_paths(user_id)
    return remote_sandbox_paths(
        user_id,
        email=email,
        display_name=display_name,
    )


async def _fetch_user_profile(user_id: str) -> tuple[str | None, str | None]:
    from app.core.db.postgres import get_async_session_factory
    from app.modules.user.model import User

    factory = get_async_session_factory()
    async with factory() as session:
        user = await session.get(User, UUID(user_id))
        if user is None:
            return None, None
        return user.email, user.display_name


def load_sandbox_paths(user_id: str) -> SandboxUserPaths:
    """Resolve paths, loading email/display_name from Postgres when needed."""
    email: str | None = None
    display_name: str | None = None
    try:
        try:
            asyncio.get_running_loop()
            in_async_context = True
        except RuntimeError:
            in_async_context = False

        if in_async_context:
            import concurrent.futures

            def _run_in_thread() -> tuple[str | None, str | None]:
                return asyncio.run(_fetch_user_profile(user_id))

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                email, display_name = pool.submit(_run_in_thread).result(timeout=15)
        else:
            email, display_name = asyncio.run(_fetch_user_profile(user_id))
    except Exception:
        logger.exception("sandbox_paths_user_lookup_failed user_id=%s", user_id)
        email, display_name = None, None
    return resolve_sandbox_paths(
        user_id,
        email=email,
        display_name=display_name,
    )
