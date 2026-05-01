"""Single source of truth for the deep agent's local workspace directory.

Used by:
- ``app.ai.backend.factory`` to root the LocalShellBackend.
- ``app.ai.backend.workspace_fs`` for the local FS reader.
- ``app.api.v1.workspace`` to expose the file tree / contents over HTTP.

The path is anchored to this file's location so it's stable regardless of the
process's cwd. Files live at ``backend_fastapi/app/ai/workspace/`` (a sibling
of this ``backend/`` package).
"""

from __future__ import annotations

from pathlib import Path

WORKSPACE_DIR: Path = (Path(__file__).resolve().parent.parent / "workspace").resolve()


def ensure_workspace() -> Path:
    """Create the workspace if missing and return its absolute path."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_DIR


def resolve_within_workspace(rel_path: str) -> Path:
    """Resolve a relative path strictly inside the workspace.

    Raises ValueError on traversal (``..``), absolute paths, or anything that
    would escape ``WORKSPACE_DIR``.
    """
    cleaned = (rel_path or "").strip().lstrip("/")
    if cleaned in {"", "."}:
        return WORKSPACE_DIR

    candidate = (WORKSPACE_DIR / cleaned).resolve()
    try:
        candidate.relative_to(WORKSPACE_DIR)
    except ValueError as exc:
        raise ValueError("path escapes workspace root") from exc
    return candidate
