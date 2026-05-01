"""Read-only abstraction over the deep agent's workspace filesystem.

Two implementations:
- ``LocalWorkspaceFS`` reads from ``app/ai/workspace/`` on the host.
- ``SandboxWorkspaceFS`` reads from the Modal sandbox via the agent's backend
  (``backend.execute`` for the tree, ``backend.read`` for file contents).

Both expose the same shape so the workspace HTTP API is backend-agnostic. The
selection mirrors ``settings.DEEP_AGENT_BACKEND``.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.ai.backend import active_backend
from app.ai.backend.workspace_paths import (
    WORKSPACE_DIR,
    ensure_workspace,
    resolve_within_workspace,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Public types ────────────────────────────────────────────────────────────


@dataclass(slots=True)
class FsEntry:
    name: str
    path: str  # workspace-relative POSIX path, no leading slash
    type: str  # "file" | "directory"
    size: int = 0
    modified_at: float | None = None


@dataclass(slots=True)
class FsFile:
    path: str  # workspace-relative POSIX path
    size: int
    modified_at: float | None
    content: str
    truncated: bool = False
    binary: bool = False


class WorkspaceFsError(Exception):
    """Raised for invalid path / not-found / read failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code  # "invalid_path" | "not_found" | "read_failed"


# Server-side caps mirror the local impl.
_MAX_ENTRIES = 5000
_MAX_FILE_BYTES = 512 * 1024  # 512 KiB
_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    "dist",
    "build",
    ".turbo",
    ".cache",
}


class WorkspaceFS(Protocol):
    def list_tree(self, rel_path: str = "") -> list[FsEntry]: ...
    def read_file(self, rel_path: str) -> FsFile: ...


# ── Local implementation ────────────────────────────────────────────────────


class LocalWorkspaceFS:
    """Reads directly from ``app/ai/workspace/`` on the host."""

    def list_tree(self, rel_path: str = "") -> list[FsEntry]:
        ensure_workspace()
        try:
            start = resolve_within_workspace(rel_path)
        except ValueError as exc:
            raise WorkspaceFsError("invalid_path", str(exc)) from None
        if not start.exists() or not start.is_dir():
            raise WorkspaceFsError("not_found", "Directory not found")

        entries: list[FsEntry] = []
        truncated = False

        def walk(directory: Path) -> None:
            nonlocal truncated
            if truncated:
                return
            try:
                children = sorted(
                    directory.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except (PermissionError, OSError):
                return
            for child in children:
                if child.name in _SKIP_DIRS:
                    continue
                if len(entries) >= _MAX_ENTRIES:
                    truncated = True
                    return
                try:
                    stat = child.stat()
                except OSError:
                    continue
                is_dir = child.is_dir()
                entries.append(
                    FsEntry(
                        name=child.name,
                        path=child.relative_to(WORKSPACE_DIR).as_posix(),
                        type="directory" if is_dir else "file",
                        size=0 if is_dir else int(stat.st_size),
                        modified_at=stat.st_mtime,
                    )
                )
                if is_dir:
                    walk(child)

        walk(start)
        if truncated:
            logger.warning("local_workspace_tree_truncated max=%s", _MAX_ENTRIES)
        return entries

    def read_file(self, rel_path: str) -> FsFile:
        ensure_workspace()
        try:
            target = resolve_within_workspace(rel_path)
        except ValueError as exc:
            raise WorkspaceFsError("invalid_path", str(exc)) from None
        if not target.exists() or not target.is_file():
            raise WorkspaceFsError("not_found", "File not found")
        try:
            stat = target.stat()
        except OSError as exc:
            raise WorkspaceFsError("read_failed", f"Stat failed: {exc}") from None

        rel = target.relative_to(WORKSPACE_DIR).as_posix()
        if stat.st_size > _MAX_FILE_BYTES:
            return FsFile(
                path=rel,
                size=int(stat.st_size),
                modified_at=stat.st_mtime,
                content=f"[file too large to preview: {stat.st_size} bytes]",
                truncated=True,
                binary=False,
            )
        try:
            raw = target.read_bytes()
        except OSError as exc:
            raise WorkspaceFsError("read_failed", f"Read failed: {exc}") from None
        if b"\x00" in raw:
            return FsFile(
                path=rel,
                size=int(stat.st_size),
                modified_at=stat.st_mtime,
                content="[binary file]",
                truncated=False,
                binary=True,
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        return FsFile(
            path=rel,
            size=int(stat.st_size),
            modified_at=stat.st_mtime,
            content=text,
            truncated=False,
            binary=False,
        )


# ── Sandbox implementation ──────────────────────────────────────────────────


_TREE_SCRIPT = """python3 -c "
import os, json, sys

SKIP = {skip!r}
ROOT = {root!r}
MAX = {max_entries}

if not os.path.isdir(ROOT):
    print(json.dumps({{'error': 'root_missing'}}))
    sys.exit(0)

entries = []
truncated = False
for dirpath, dirnames, filenames in os.walk(ROOT, followlinks=False):
    dirnames[:] = sorted([d for d in dirnames if d not in SKIP], key=str.lower)
    for d in dirnames:
        if len(entries) >= MAX:
            truncated = True
            break
        full = os.path.join(dirpath, d)
        try: st = os.stat(full)
        except OSError: continue
        entries.append({{'path': os.path.relpath(full, ROOT), 'type': 'directory', 'size': 0, 'mtime': st.st_mtime}})
    if truncated: break
    for f in sorted(filenames, key=str.lower):
        if len(entries) >= MAX:
            truncated = True
            break
        full = os.path.join(dirpath, f)
        try: st = os.stat(full)
        except OSError: continue
        entries.append({{'path': os.path.relpath(full, ROOT), 'type': 'file', 'size': st.st_size, 'mtime': st.st_mtime}})
    if truncated: break

print(json.dumps({{'entries': entries, 'truncated': truncated}}))
" 2>/dev/null
"""


class SandboxWorkspaceFS:
    """Reads from the Modal sandbox via the deep agent's ``ModalSandbox`` backend.

    Tree and file ops are dispatched to the sandbox using the same ``execute``
    plumbing the agent uses, so the UI shows exactly what the agent sees.
    """

    def __init__(self) -> None:
        self._workdir = settings.DEEP_AGENT_SANDBOX_WORKDIR or "/workspace"

    def _backend(self):
        # Imported lazily so this module can be imported even when
        # langchain_modal isn't usable (no token, etc.).
        from app.ai.backend.sandbox import get_sandbox_backend

        return get_sandbox_backend()

    def _abs(self, rel_path: str) -> str:
        cleaned = (rel_path or "").strip().lstrip("/")
        if cleaned in {"", "."}:
            return self._workdir
        if ".." in cleaned.split("/"):
            raise WorkspaceFsError("invalid_path", "Path traversal not allowed")
        return f"{self._workdir.rstrip('/')}/{cleaned}"

    def list_tree(self, rel_path: str = "") -> list[FsEntry]:
        start = self._abs(rel_path)
        backend = self._backend()
        cmd = _TREE_SCRIPT.format(
            skip=set(_SKIP_DIRS),
            root=start,
            max_entries=_MAX_ENTRIES,
        )
        result = backend.execute(cmd)
        out = (result.output or "").strip()
        if not out:
            raise WorkspaceFsError("read_failed", "empty response from sandbox")
        try:
            data = json.loads(out.split("\n")[-1])
        except json.JSONDecodeError as exc:
            raise WorkspaceFsError(
                "read_failed", f"unparseable sandbox response: {exc}"
            ) from None
        if isinstance(data, dict) and data.get("error") == "root_missing":
            # Empty workspace – treat as no entries so the UI shows "No files".
            return []
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            raise WorkspaceFsError("read_failed", "unexpected sandbox response shape")
        if data.get("truncated"):
            logger.warning("sandbox_workspace_tree_truncated max=%s", _MAX_ENTRIES)

        entries: list[FsEntry] = []
        for item in data["entries"]:
            try:
                rel = str(item["path"]).replace("\\", "/")
                entries.append(
                    FsEntry(
                        name=rel.split("/")[-1],
                        path=rel,
                        type="directory" if item["type"] == "directory" else "file",
                        size=int(item.get("size", 0) or 0),
                        modified_at=float(item["mtime"]) if item.get("mtime") else None,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return entries

    def read_file(self, rel_path: str) -> FsFile:
        abs_path = self._abs(rel_path)
        backend = self._backend()
        # Use the sandbox's own paginated ``read`` (returns base64 for binary,
        # utf-8 text otherwise). Limit big enough to cover ~500KB single-shot.
        result = backend.read(abs_path, offset=0, limit=10_000_000)
        if result.error:
            raise WorkspaceFsError("not_found", result.error)
        file_data = result.file_data
        if file_data is None:
            raise WorkspaceFsError("read_failed", "no file data returned")

        rel = (rel_path or "").lstrip("/")

        if file_data.encoding == "base64":
            try:
                raw = base64.b64decode(file_data.content)
                size = len(raw)
            except Exception:
                size = 0
            return FsFile(
                path=rel,
                size=size,
                modified_at=None,
                content="[binary file]",
                truncated=False,
                binary=True,
            )

        text = file_data.content or ""
        # ``read`` truncates with a trailing notice when output is too large.
        truncated = "[Output was truncated due to size limits." in text
        return FsFile(
            path=rel,
            size=len(text.encode("utf-8")),
            modified_at=None,
            content=text,
            truncated=truncated,
            binary=False,
        )


# ── Factory ─────────────────────────────────────────────────────────────────


_local_fs = LocalWorkspaceFS()
_sandbox_fs: SandboxWorkspaceFS | None = None


def get_workspace_fs() -> WorkspaceFS:
    """Return the FS implementation matching the active backend."""
    if active_backend() == "modal":
        global _sandbox_fs
        if _sandbox_fs is None:
            _sandbox_fs = SandboxWorkspaceFS()
        return _sandbox_fs
    return _local_fs
