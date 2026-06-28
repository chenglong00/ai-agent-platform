"""Read-only workspace filesystem backed by the per-user agent sandbox."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import BackendProtocol

from app.ai.chat_agent.backend_factory import get_user_backend
from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 5000
_MAX_FILE_BYTES = 512 * 1024
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


@dataclass(slots=True)
class FsEntry:
    name: str
    path: str
    type: str  # "file" | "directory"
    size: int = 0
    modified_at: float | None = None


@dataclass(slots=True)
class FsFile:
    path: str
    size: int
    modified_at: float | None
    content: str
    truncated: bool = False
    binary: bool = False


class WorkspaceFsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _parse_mtime(raw: object) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return datetime.fromisoformat(str(raw)).timestamp()
    except ValueError:
        return None


def _normalize_rel_path(path: str) -> str:
    cleaned = (path or "").strip().replace("\\", "/").lstrip("/")
    if cleaned in {"", "."}:
        return ""
    if ".." in cleaned.split("/"):
        raise WorkspaceFsError("invalid_path", "Path traversal not allowed")
    return cleaned


def _backend_rel_path(rel_path: str) -> str:
    rel = _normalize_rel_path(rel_path)
    return f"/{rel}" if rel else "/"


def _entry_name(path: str) -> str:
    return path.rstrip("/").split("/")[-1]


def _local_root_for_user(user_id: str) -> Path | None:
    backend = get_user_backend(user_id)
    if not isinstance(backend, LocalShellBackend):
        return None
    root_dir = getattr(backend, "root_dir", None) or getattr(backend, "cwd", None)
    if not root_dir:
        return None
    return Path(str(root_dir)).resolve()


def _walk_local_root(root: Path, start: Path) -> list[FsEntry]:
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
                    path=child.relative_to(root).as_posix(),
                    type="directory" if is_dir else "file",
                    size=0 if is_dir else int(stat.st_size),
                    modified_at=stat.st_mtime,
                )
            )
            if is_dir:
                walk(child)

    walk(start)
    if truncated:
        logger.warning("workspace_tree_truncated user_root=%s max=%s", root, _MAX_ENTRIES)
    return entries


def _entries_from_backend_glob(
    backend: BackendProtocol,
    rel_path: str,
) -> list[FsEntry]:
    pattern = "**/*" if not rel_path else f"{rel_path.rstrip('/')}/**/*"
    result = backend.glob(pattern)
    if result.error:
        if "not found" in result.error.lower():
            raise WorkspaceFsError("not_found", result.error)
        raise WorkspaceFsError("read_failed", result.error)

    by_path: dict[str, FsEntry] = {}
    for item in result.matches or []:
        if len(by_path) >= _MAX_ENTRIES:
            logger.warning("workspace_tree_truncated max=%s", _MAX_ENTRIES)
            break
        raw_path = str(item.get("path", "")).replace("\\", "/").lstrip("/")
        if not raw_path or raw_path.split("/")[0] in _SKIP_DIRS:
            continue
        parts = raw_path.split("/")
        for idx in range(len(parts)):
            subpath = "/".join(parts[: idx + 1])
            if subpath in by_path:
                continue
            is_dir = idx < len(parts) - 1 or bool(item.get("is_dir"))
            by_path[subpath] = FsEntry(
                name=_entry_name(subpath),
                path=subpath,
                type="directory" if is_dir else "file",
                size=0 if is_dir else int(item.get("size", 0) or 0),
                modified_at=_parse_mtime(item.get("modified_at")),
            )

    return sorted(by_path.values(), key=lambda e: (e.type != "directory", e.path.lower()))


class UserWorkspaceFS:
    """Browse the same filesystem the deep agent uses for a given user."""

    def __init__(self, user_id: str) -> None:
        self._user_id = str(user_id)

    def list_tree(self, rel_path: str = "") -> list[FsEntry]:
        normalized = _normalize_rel_path(rel_path)
        local_root = _local_root_for_user(self._user_id)
        if local_root is not None:
            start = local_root if not normalized else (local_root / normalized).resolve()
            try:
                start.relative_to(local_root)
            except ValueError as exc:
                raise WorkspaceFsError("invalid_path", "Path escapes workspace root") from exc
            return _walk_local_root(local_root, start)

        backend = get_user_backend(self._user_id)
        if normalized:
            probe = backend.ls(_backend_rel_path(normalized))
            if probe.error:
                raise WorkspaceFsError("not_found", probe.error)
        return _entries_from_backend_glob(backend, normalized)

    def read_file(self, rel_path: str) -> FsFile:
        normalized = _normalize_rel_path(rel_path)
        if not normalized:
            raise WorkspaceFsError("invalid_path", "File path is required")

        local_root = _local_root_for_user(self._user_id)
        if local_root is not None:
            target = (local_root / normalized).resolve()
            try:
                target.relative_to(local_root)
            except ValueError as exc:
                raise WorkspaceFsError("invalid_path", "Path escapes workspace root") from exc
            if not target.exists() or not target.is_file():
                raise WorkspaceFsError("not_found", "File not found")
            try:
                stat = target.stat()
            except OSError as exc:
                raise WorkspaceFsError("read_failed", f"Stat failed: {exc}") from None
            if stat.st_size > _MAX_FILE_BYTES:
                return FsFile(
                    path=normalized,
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
                    path=normalized,
                    size=int(stat.st_size),
                    modified_at=stat.st_mtime,
                    content="[binary file]",
                    binary=True,
                )
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
            return FsFile(
                path=normalized,
                size=int(stat.st_size),
                modified_at=stat.st_mtime,
                content=text,
            )

        backend = get_user_backend(self._user_id)
        result = backend.read(_backend_rel_path(normalized))
        if result.error:
            raise WorkspaceFsError("not_found", result.error)
        file_data = result.file_data
        if file_data is None:
            raise WorkspaceFsError("read_failed", "No file data returned")

        if file_data.encoding == "base64":
            try:
                raw = base64.b64decode(file_data.content)
                size = len(raw)
            except Exception:
                size = 0
            return FsFile(
                path=normalized,
                size=size,
                modified_at=None,
                content="[binary file]",
                binary=True,
            )

        text = file_data.content or ""
        truncated = "[Output was truncated due to size limits." in text
        if len(text.encode("utf-8")) > _MAX_FILE_BYTES:
            truncated = True
        return FsFile(
            path=normalized,
            size=len(text.encode("utf-8")),
            modified_at=None,
            content=text,
            truncated=truncated,
        )


def workspace_root_label(user_id: str) -> str:
    """Human-readable workspace root for UI hints."""
    local_root = _local_root_for_user(user_id)
    if local_root is not None:
        return str(local_root)
    backend_name = settings.DEEP_AGENT_BACKEND.strip().lower()
    workdir = settings.DEEP_AGENT_SANDBOX_WORKDIR or "/workspace"
    return f"{backend_name}:{workdir} (user {user_id})"
