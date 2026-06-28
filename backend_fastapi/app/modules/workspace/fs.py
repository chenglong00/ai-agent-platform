"""Read-only workspace filesystem backed by the per-user agent sandbox."""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from deepagents.backends.protocol import BackendProtocol, ExecuteResponse

from app.ai.chat_agent.backend_factory import get_user_backend
from app.ai.chat_agent.sandbox_paths import load_sandbox_paths
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


def _normalize_rel_path(path: str) -> str:
    cleaned = (path or "").strip().replace("\\", "/").lstrip("/")
    if cleaned in {"", "."}:
        return ""
    if ".." in cleaned.split("/"):
        raise WorkspaceFsError("invalid_path", "Path traversal not allowed")
    return cleaned


def _entry_name(path: str) -> str:
    return path.rstrip("/").split("/")[-1]


def _is_local_backend() -> bool:
    return settings.DEEP_AGENT_BACKEND.strip().lower() == "local"


def _local_root_for_user(user_id: str) -> Path | None:
    if not _is_local_backend():
        return None
    paths = load_sandbox_paths(user_id)
    workspace = Path(paths.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def _sandbox_abs_path(user_id: str, rel_path: str) -> str:
    rel = _normalize_rel_path(rel_path)
    root = load_sandbox_paths(user_id).workspace
    if not rel:
        return root
    return f"{root}/{rel}"


def _open_user_backend(user_id: str) -> BackendProtocol:
    try:
        return get_user_backend(user_id)
    except Exception as exc:
        raise WorkspaceFsError(
            "read_failed",
            f"Could not open agent sandbox ({settings.DEEP_AGENT_BACKEND}): {exc}",
        ) from exc


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


def _sandbox_raw_execute(
    backend: BackendProtocol,
    command: str,
    *,
    timeout: int | None = 120,
) -> ExecuteResponse:
    """Execute on the underlying sandbox (bypasses user-home cd wrapper)."""
    raw = getattr(backend, "execute_sandbox_raw", None)
    if callable(raw):
        return raw(command, timeout=timeout)
    inner = getattr(backend, "_inner", backend)
    exec_fn = getattr(inner, "execute", None)
    if exec_fn is None:
        raise WorkspaceFsError("read_failed", "Sandbox backend cannot execute commands")
    if timeout is not None:
        return exec_fn(command, timeout=timeout)
    return exec_fn(command)


def _strip_sandbox_noise(output: str) -> str:
    """Remove Daytona stderr wrappers and other non-JSON noise."""
    cleaned = re.sub(r"\n<stderr>.*?</stderr>", "", output, flags=re.DOTALL)
    return cleaned.strip()


def _parse_listing_payload(output: str) -> dict:
    text = _strip_sandbox_noise(output)
    if not text:
        raise json.JSONDecodeError("empty output", "", 0)
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return json.loads(text)


def _workspace_listing_command(root: str, skip: list[str]) -> str:
    """Base64-wrapped Python listing (avoids shell quoting issues)."""
    py = f"""import json, os, sys
SKIP = set({skip!r})
ROOT = {root!r}
MAX = {_MAX_ENTRIES}
if not os.path.isdir(ROOT):
    print(json.dumps({{"entries": [], "truncated": False}}))
    sys.exit(0)
entries = []
truncated = False
for dirpath, dirnames, filenames in os.walk(ROOT, followlinks=False):
    dirnames[:] = sorted([d for d in dirnames if d not in SKIP], key=str.lower)
    rel_dir = os.path.relpath(dirpath, ROOT)
    if rel_dir != '.':
        if len(entries) >= MAX:
            truncated = True
            break
        try:
            st = os.stat(dirpath)
            entries.append({{"path": rel_dir, "type": "directory", "size": 0, "mtime": st.st_mtime}})
        except OSError:
            pass
    for f in sorted(filenames, key=str.lower):
        if len(entries) >= MAX:
            truncated = True
            break
        full = os.path.join(dirpath, f)
        try:
            st = os.stat(full)
        except OSError:
            continue
        rel = os.path.relpath(full, ROOT)
        entries.append({{"path": rel, "type": "file", "size": st.st_size, "mtime": st.st_mtime}})
    if truncated:
        break
print(json.dumps({{"entries": entries, "truncated": truncated}}))
"""
    encoded = base64.b64encode(py.encode("utf-8")).decode("ascii")
    runner = f"import base64; exec(base64.b64decode('{encoded}').decode())"
    return (
        f"python3 -c {json.dumps(runner)} 2>/dev/null "
        f"|| python -c {json.dumps(runner)} 2>/dev/null"
    )


def _read_file_from_sandbox_execute(
    backend: BackendProtocol,
    user_id: str,
    normalized: str,
) -> FsFile:
    """Read a file via sandbox shell — same transport as tree listing."""
    ensure = getattr(backend, "ensure_user_root", None)
    if callable(ensure):
        ensure()

    abs_path = _sandbox_abs_path(user_id, normalized)
    py = f"""import json, os, sys
path = {abs_path!r}
if not os.path.isfile(path):
    print(json.dumps({{"error": "not_found"}}))
    sys.exit(0)
with open(path, "rb") as f:
    raw = f.read()
if b"\\x00" in raw:
    print(json.dumps({{"binary": True, "size": len(raw)}}))
    sys.exit(0)
if len(raw) > {_MAX_FILE_BYTES}:
    text = raw[:{_MAX_FILE_BYTES}].decode("utf-8", errors="replace")
    print(json.dumps({{"content": text, "size": len(raw), "truncated": True}}))
    sys.exit(0)
try:
    text = raw.decode("utf-8")
except UnicodeDecodeError:
    text = raw.decode("utf-8", errors="replace")
print(json.dumps({{"content": text, "size": len(raw), "truncated": False}}))
"""
    encoded = base64.b64encode(py.encode("utf-8")).decode("ascii")
    runner = f"import base64; exec(base64.b64decode('{encoded}').decode())"
    command = (
        f"python3 -c {json.dumps(runner)} 2>/dev/null "
        f"|| python -c {json.dumps(runner)} 2>/dev/null"
    )
    result = _sandbox_raw_execute(backend, command)
    out = result.output or ""
    if result.exit_code not in (0, None) and not out.strip():
        raise WorkspaceFsError(
            "read_failed",
            f"Sandbox read failed (exit {result.exit_code})",
        )
    try:
        data = _parse_listing_payload(out)
    except json.JSONDecodeError as exc:
        snippet = _strip_sandbox_noise(out)[:240]
        logger.warning(
            "sandbox_read_parse_failed user_id=%s path=%s exit=%s snippet=%r",
            user_id,
            abs_path,
            result.exit_code,
            snippet,
        )
        raise WorkspaceFsError(
            "read_failed",
            f"Could not parse sandbox read response: {exc}",
        ) from None

    if not isinstance(data, dict):
        raise WorkspaceFsError("read_failed", "Unexpected sandbox read response")
    if data.get("error") == "not_found":
        raise WorkspaceFsError("not_found", f"File not found: {normalized}")
    if data.get("binary"):
        return FsFile(
            path=normalized,
            size=int(data.get("size", 0) or 0),
            modified_at=None,
            content="[binary file]",
            binary=True,
        )

    text = str(data.get("content") or "")
    size = int(data.get("size", len(text.encode("utf-8"))) or 0)
    return FsFile(
        path=normalized,
        size=size,
        modified_at=None,
        content=text,
        truncated=bool(data.get("truncated")),
    )


def _entries_from_sandbox_execute(
    backend: BackendProtocol,
    user_id: str,
    rel_path: str,
) -> list[FsEntry]:
    """List files via sandbox shell — Daytona/Modal glob+ls can hang indefinitely."""
    ensure = getattr(backend, "ensure_user_root", None)
    if callable(ensure):
        ensure()

    start = _sandbox_abs_path(user_id, rel_path)
    skip = sorted(_SKIP_DIRS)
    command = _workspace_listing_command(start, skip)
    result = _sandbox_raw_execute(backend, command)
    out = result.output or ""
    if result.exit_code not in (0, None) and not out.strip():
        raise WorkspaceFsError(
            "read_failed",
            f"Sandbox listing failed (exit {result.exit_code})",
        )
    try:
        data = _parse_listing_payload(out)
    except json.JSONDecodeError as exc:
        snippet = _strip_sandbox_noise(out)[:240]
        logger.warning(
            "sandbox_listing_parse_failed user_id=%s root=%s exit=%s snippet=%r",
            user_id,
            start,
            result.exit_code,
            snippet,
        )
        raise WorkspaceFsError(
            "read_failed",
            f"Could not parse sandbox listing: {exc}",
        ) from None
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise WorkspaceFsError("read_failed", "Unexpected sandbox listing response")
    if data.get("truncated"):
        logger.warning("sandbox_workspace_tree_truncated max=%s", _MAX_ENTRIES)

    entries: list[FsEntry] = []
    for item in data["entries"]:
        try:
            rel = str(item["path"]).replace("\\", "/")
            entries.append(
                FsEntry(
                    name=_entry_name(rel),
                    path=rel,
                    type="directory" if item["type"] == "directory" else "file",
                    size=int(item.get("size", 0) or 0),
                    modified_at=float(item["mtime"]) if item.get("mtime") else None,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return entries


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

        backend = _open_user_backend(self._user_id)
        return _entries_from_sandbox_execute(backend, self._user_id, normalized)

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

        backend = _open_user_backend(self._user_id)
        return _read_file_from_sandbox_execute(backend, self._user_id, normalized)


def workspace_root_label(user_id: str) -> str:
    """Human-readable workspace root for UI hints (does not touch the sandbox)."""
    backend_name = settings.DEEP_AGENT_BACKEND.strip().lower()
    paths = load_sandbox_paths(user_id)
    return f"{backend_name}:{paths.workspace}"
