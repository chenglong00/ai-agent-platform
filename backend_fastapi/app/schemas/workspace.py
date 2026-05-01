"""Schemas for the deep-agent workspace browser API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class WorkspaceEntry(BaseModel):
    name: str
    path: str  # workspace-relative, no leading slash, "/" for nested dirs
    type: Literal["file", "directory"]
    size: int = 0
    modified_at: float | None = None  # epoch seconds


class WorkspaceTreeResponse(BaseModel):
    root: str  # always ""
    entries: list[WorkspaceEntry]


class WorkspaceFileResponse(BaseModel):
    path: str
    size: int
    modified_at: float | None
    content: str
    truncated: bool = False
    binary: bool = False
