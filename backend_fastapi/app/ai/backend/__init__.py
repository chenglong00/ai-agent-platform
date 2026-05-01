"""Deep agent backend & workspace plumbing.

Modules:
- ``workspace_paths`` — source of truth for the local workspace directory.
- ``factory`` — :func:`build_backend` picks a deepagents backend (local or
  modal) based on :data:`settings.DEEP_AGENT_BACKEND`.
- ``sandbox`` — process-wide Modal sandbox singleton (lazy create / reset).
- ``workspace_fs`` — read-only FS abstraction (local or sandbox) consumed by
  the workspace HTTP router (lives at :mod:`app.api.v1.workspace`).

The :func:`active_backend` helper here normalizes the env-driven choice into
the literal ``"local"`` or ``"modal"`` string used by every other module.
"""

from __future__ import annotations

from typing import Literal

from app.core.config import settings

BackendChoice = Literal["local", "modal"]


def active_backend() -> BackendChoice:
    """Return the active backend choice, normalized.

    Defaults to ``"local"``. Any unknown value also collapses to ``"local"``.
    """
    choice = (settings.DEEP_AGENT_BACKEND or "local").strip().lower()
    return "modal" if choice == "modal" else "local"


__all__ = ["BackendChoice", "active_backend"]
