"""Workspace service facade."""

from __future__ import annotations

from app.modules.workspace.fs import (
    FsEntry,
    FsFile,
    UserWorkspaceFS,
    WorkspaceFsError,
    workspace_root_label,
)

WorkspaceServiceError = WorkspaceFsError

__all__ = [
    "FsEntry",
    "FsFile",
    "WorkspaceService",
    "WorkspaceServiceError",
    "get_workspace_service",
    "workspace_root_label",
]


class WorkspaceService:
    def __init__(self, user_id: str) -> None:
        self._fs = UserWorkspaceFS(user_id)

    def list_tree(self, path: str = "") -> list[FsEntry]:
        return self._fs.list_tree(path)

    def read_file(self, path: str) -> FsFile:
        return self._fs.read_file(path)


def get_workspace_service(user_id: str) -> WorkspaceService:
    return WorkspaceService(user_id)
