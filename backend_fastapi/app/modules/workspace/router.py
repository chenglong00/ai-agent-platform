"""Workspace API — browse the per-user deep agent sandbox."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.modules.auth.rbac import RequireUser
from app.modules.user.schema import UserResponse
from app.modules.workspace.schema import (
    WorkspaceEntry,
    WorkspaceFileResponse,
    WorkspaceTreeResponse,
)
from app.modules.workspace.service import (
    WorkspaceServiceError,
    get_workspace_service,
    workspace_root_label,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_FS_ERROR_STATUS = {"invalid_path": 400, "not_found": 404}


def _http_from_service_error(exc: WorkspaceServiceError) -> HTTPException:
    return HTTPException(
        status_code=_FS_ERROR_STATUS.get(exc.code, 500),
        detail=str(exc),
    )


@router.get("/root")
async def get_workspace_root(
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> dict[str, str]:
    """Return the resolved workspace root for the current user."""
    return {
        "root": workspace_root_label(str(current_user.id)),
        "backend": settings.DEEP_AGENT_BACKEND.strip().lower(),
    }


@router.get("/tree", response_model=WorkspaceTreeResponse)
async def get_workspace_tree(
    current_user: Annotated[UserResponse, Depends(RequireUser)],
    path: Annotated[str, Query(description="Workspace-relative directory; '' for root")] = "",
) -> WorkspaceTreeResponse:
    service = get_workspace_service(str(current_user.id))
    try:
        rows = service.list_tree(path)
    except WorkspaceServiceError as exc:
        raise _http_from_service_error(exc) from None
    except Exception as exc:
        logger.exception(
            "workspace_tree_failed user_id=%s backend=%s",
            current_user.id,
            settings.DEEP_AGENT_BACKEND,
        )
        raise HTTPException(status_code=502, detail=f"Workspace backend error: {exc}") from None
    return WorkspaceTreeResponse(
        root="",
        entries=[
            WorkspaceEntry(
                name=e.name,
                path=e.path,
                type="directory" if e.type == "directory" else "file",
                size=e.size,
                modified_at=e.modified_at,
            )
            for e in rows
        ],
    )


@router.get("/file", response_model=WorkspaceFileResponse)
async def get_workspace_file(
    current_user: Annotated[UserResponse, Depends(RequireUser)],
    path: Annotated[str, Query(description="Workspace-relative file path")],
) -> WorkspaceFileResponse:
    service = get_workspace_service(str(current_user.id))
    try:
        f = service.read_file(path)
    except WorkspaceServiceError as exc:
        raise _http_from_service_error(exc) from None
    except Exception as exc:
        logger.exception(
            "workspace_file_failed user_id=%s backend=%s path=%s",
            current_user.id,
            settings.DEEP_AGENT_BACKEND,
            path,
        )
        raise HTTPException(status_code=502, detail=f"Workspace backend error: {exc}") from None
    return WorkspaceFileResponse(
        path=f.path,
        size=f.size,
        modified_at=f.modified_at,
        content=f.content,
        truncated=f.truncated,
        binary=f.binary,
    )
