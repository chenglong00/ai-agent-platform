"""Scope a shared sandbox backend to one user's directory."""

from __future__ import annotations

import shlex
from typing import Any

from app.ai.chat_agent.sandbox_shell import ensure_directory_command
from deepagents.backends.protocol import (
    EditResult,
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
    GlobResult,
    GrepResult,
    LsResult,
    ReadResult,
    SandboxBackendProtocol,
    WriteResult,
)




class UserScopedSandboxBackend(SandboxBackendProtocol):
    """Maps agent-visible paths into a per-user folder on a shared sandbox."""

    def __init__(
        self,
        inner: SandboxBackendProtocol,
        *,
        user_id: str,
        user_root: str,
        execute_cwd: str | None = None,
        home: str | None = None,
    ) -> None:
        self._inner = inner
        self._user_id = str(user_id)
        self._user_root = user_root.rstrip("/")
        self._home = (home or user_root).rstrip("/")
        self._execute_cwd = (execute_cwd or user_root).rstrip("/")

    @property
    def id(self) -> str:
        return f"{self._inner.id}:{self._user_id}"

    def _map_in(self, path: str | None) -> str | None:
        if path is None:
            return self._user_root
        cleaned = path if path.startswith("/") else f"/{path}"
        if cleaned.startswith("/workspace/"):
            cleaned = f"/{cleaned[len('/workspace/'):]}"
        if cleaned == self._user_root or cleaned.startswith(f"{self._user_root}/"):
            return cleaned
        rel = cleaned.lstrip("/")
        return f"{self._user_root}/{rel}" if rel else self._user_root

    def _map_out(self, path: str) -> str:
        prefix = f"{self._user_root}/"
        if path == self._user_root:
            return "/"
        if path.startswith(prefix):
            return f"/{path[len(prefix):]}"
        return path

    def _map_ls_entries(self, result: LsResult) -> LsResult:
        if result.error or not result.entries:
            return result
        mapped = []
        for entry in result.entries:
            item = dict(entry)
            if "path" in item:
                item["path"] = self._map_out(str(item["path"]))
            mapped.append(item)
        return LsResult(error=result.error, entries=mapped)

    def _map_glob_matches(self, result: GlobResult) -> GlobResult:
        if result.error or not result.matches:
            return result
        mapped = []
        for entry in result.matches:
            item = dict(entry)
            if "path" in item:
                item["path"] = self._map_out(str(item["path"]))
            mapped.append(item)
        return GlobResult(error=result.error, matches=mapped)

    def _map_grep_matches(self, result: GrepResult) -> GrepResult:
        if result.error or not result.matches:
            return result
        mapped = []
        for entry in result.matches:
            item = dict(entry)
            if "path" in item:
                item["path"] = self._map_out(str(item["path"]))
            mapped.append(item)
        return GrepResult(error=result.error, matches=mapped)

    def ensure_user_root(self) -> None:
        """Create home + workspace on the shared VM (with sudo fallback on Daytona)."""
        self._inner.execute(ensure_directory_command(self._home))
        self._inner.execute(ensure_directory_command(self._user_root))
        if self._execute_cwd not in {self._user_root, self._home}:
            self._inner.execute(ensure_directory_command(self._execute_cwd))

    def ls(self, path: str) -> LsResult:
        return self._map_ls_entries(self._inner.ls(self._map_in(path) or self._user_root))

    async def als(self, path: str) -> LsResult:
        return self._map_ls_entries(await self._inner.als(self._map_in(path) or self._user_root))

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        return self._inner.read(self._map_in(file_path) or self._user_root, offset, limit)

    async def aread(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> ReadResult:
        return await self._inner.aread(self._map_in(file_path) or self._user_root, offset, limit)

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> GrepResult:
        return self._map_grep_matches(
            self._inner.grep(pattern, self._map_in(path), glob),
        )

    async def agrep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> GrepResult:
        return self._map_grep_matches(
            await self._inner.agrep(pattern, self._map_in(path), glob),
        )

    def glob(self, pattern: str, path: str = "/") -> GlobResult:
        return self._map_glob_matches(
            self._inner.glob(pattern, self._map_in(path) or self._user_root),
        )

    async def aglob(self, pattern: str, path: str = "/") -> GlobResult:
        return self._map_glob_matches(
            await self._inner.aglob(pattern, self._map_in(path) or self._user_root),
        )

    def write(self, file_path: str, content: str) -> WriteResult:
        result = self._inner.write(self._map_in(file_path) or self._user_root, content)
        if result.path:
            return WriteResult(error=result.error, path=self._map_out(result.path))
        return result

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        result = await self._inner.awrite(self._map_in(file_path) or self._user_root, content)
        if result.path:
            return WriteResult(error=result.error, path=self._map_out(result.path))
        return result

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        result = self._inner.edit(
            self._map_in(file_path) or self._user_root,
            old_string,
            new_string,
            replace_all,
        )
        if result.path:
            return EditResult(
                error=result.error,
                path=self._map_out(result.path),
                occurrences=result.occurrences,
            )
        return result

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        result = await self._inner.aedit(
            self._map_in(file_path) or self._user_root,
            old_string,
            new_string,
            replace_all,
        )
        if result.path:
            return EditResult(
                error=result.error,
                path=self._map_out(result.path),
                occurrences=result.occurrences,
            )
        return result

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        mapped = [(self._map_in(path) or self._user_root, content) for path, content in files]
        responses = self._inner.upload_files(mapped)
        out: list[FileUploadResponse] = []
        for (orig_path, _), resp in zip(files, responses, strict=False):
            out.append(FileUploadResponse(path=orig_path, error=resp.error))
        return out

    async def aupload_files(
        self,
        files: list[tuple[str, bytes]],
    ) -> list[FileUploadResponse]:
        mapped = [(self._map_in(path) or self._user_root, content) for path, content in files]
        responses = await self._inner.aupload_files(mapped)
        out: list[FileUploadResponse] = []
        for (orig_path, _), resp in zip(files, responses, strict=False):
            out.append(FileUploadResponse(path=orig_path, error=resp.error))
        return out

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        mapped = [self._map_in(path) or self._user_root for path in paths]
        responses = self._inner.download_files(mapped)
        out: list[FileDownloadResponse] = []
        for orig_path, resp in zip(paths, responses, strict=False):
            out.append(
                FileDownloadResponse(path=orig_path, content=resp.content, error=resp.error),
            )
        return out

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        mapped = [self._map_in(path) or self._user_root for path in paths]
        responses = await self._inner.adownload_files(mapped)
        out: list[FileDownloadResponse] = []
        for orig_path, resp in zip(paths, responses, strict=False):
            out.append(
                FileDownloadResponse(path=orig_path, content=resp.content, error=resp.error),
            )
        return out

    def execute_sandbox_raw(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        """Run a command in the sandbox without cd into the user home."""
        if timeout is None:
            return self._inner.execute(command)
        return self._inner.execute(command, timeout=timeout)

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        wrapped = f"cd {shlex.quote(self._execute_cwd)} && {command}"
        if timeout is None:
            return self._inner.execute(wrapped)
        return self._inner.execute(wrapped, timeout=timeout)

    async def aexecute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        wrapped = f"cd {shlex.quote(self._execute_cwd)} && {command}"
        if timeout is None:
            return await self._inner.aexecute(wrapped)
        return await self._inner.aexecute(wrapped, timeout=timeout)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
