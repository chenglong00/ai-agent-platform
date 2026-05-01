"""Workspace service — public facade routes depend on.

Route handlers should depend on this module rather than reaching into
``app.ai.backend.workspace_fs`` directly. The facade:

- hides which deepagents backend is active (local dir vs Modal sandbox);
- exposes a stable surface (``WorkspaceService`` + ``WorkspaceServiceError``)
  even if the underlying adapters change;
- gives us one place to add service-level concerns later — caching, audit
  logging, rate limiting, per-user scoping, etc.

The actual filesystem readers live with the agent backend in
:mod:`app.ai.backend.workspace_fs`, since they're tightly coupled to the
concrete deepagents backend (``LocalShellBackend`` / ``ModalSandbox``).
"""

from __future__ import annotations

from app.ai.backend.workspace_fs import (
    FsEntry,
    FsFile,
    WorkspaceFS,
    WorkspaceFsError as WorkspaceServiceError,
    get_workspace_fs,
)

__all__ = [
    "FsEntry",
    "FsFile",
    "WorkspaceService",
    "WorkspaceServiceError",
    "get_workspace_service",
]


class WorkspaceService:
    """Backend-agnostic facade for workspace browsing.

    Wraps a :class:`WorkspaceFS` adapter and forwards calls. Today this is a
    pure pass-through; keep it that way unless you genuinely need a
    service-level concern (e.g. caching, audit logging) — adapters belong in
    :mod:`app.ai.backend.workspace_fs`.
    """

    def __init__(self, fs: WorkspaceFS) -> None:
        self._fs = fs

    def list_tree(self, path: str = "") -> list[FsEntry]:
        """Return a recursive tree under ``path`` (workspace-relative, ``''`` for root)."""
        return self._fs.list_tree(path)

    def read_file(self, path: str) -> FsFile:
        """Return file contents and metadata for the workspace-relative ``path``."""
        return self._fs.read_file(path)


def get_workspace_service() -> WorkspaceService:
    """Return a :class:`WorkspaceService` bound to the currently active backend."""
    return WorkspaceService(get_workspace_fs())
