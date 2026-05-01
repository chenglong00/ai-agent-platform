"""Workspace API: browse and read files inside the deep agent's workspace.

Routes delegate to :mod:`app.services.workspace_service`, which hides whether
the underlying backend is the local workspace dir or the Modal sandbox
(selected via ``settings.DEEP_AGENT_BACKEND``).

Security:
- All routes require an authenticated user (``RequireUser``).
- The sandbox-reset route requires admin (``RequireAdmin``) since terminating
  the sandbox affects every active chat.
- Path resolution rejects traversal (``..``) and absolute paths that would
  escape the workspace root.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.ai.backend import active_backend
from app.core.config import settings
from app.core.dependency import RequireAdmin, RequireUser
from app.schemas.user import UserResponse
from app.schemas.workspace import (
    WorkspaceEntry,
    WorkspaceFileResponse,
    WorkspaceTreeResponse,
)
from app.services.workspace_service import (
    WorkspaceServiceError,
    get_workspace_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


_FS_ERROR_STATUS = {"invalid_path": 400, "not_found": 404}


def _http_from_service_error(exc: WorkspaceServiceError) -> HTTPException:
    return HTTPException(
        status_code=_FS_ERROR_STATUS.get(exc.code, 500),
        detail=str(exc),
    )


@router.get("/tree", response_model=WorkspaceTreeResponse)
async def get_workspace_tree(
    _current_user: Annotated[UserResponse, Depends(RequireUser)],
    path: Annotated[str, Query(description="Workspace-relative directory; '' for root")] = "",
) -> WorkspaceTreeResponse:
    """Recursive listing of files and directories under the workspace root."""
    service = get_workspace_service()
    try:
        rows = service.list_tree(path)
    except WorkspaceServiceError as exc:
        raise _http_from_service_error(exc) from None
    except Exception as exc:
        logger.exception("workspace_tree_failed backend=%s", settings.DEEP_AGENT_BACKEND)
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
    _current_user: Annotated[UserResponse, Depends(RequireUser)],
    path: Annotated[str, Query(description="Workspace-relative file path")],
) -> WorkspaceFileResponse:
    """Read a file's contents (UTF-8 text). Binary or oversized files are flagged."""
    service = get_workspace_service()
    try:
        f = service.read_file(path)
    except WorkspaceServiceError as exc:
        raise _http_from_service_error(exc) from None
    except Exception as exc:
        logger.exception("workspace_file_failed backend=%s", settings.DEEP_AGENT_BACKEND)
        raise HTTPException(status_code=502, detail=f"Workspace backend error: {exc}") from None
    return WorkspaceFileResponse(
        path=f.path,
        size=f.size,
        modified_at=f.modified_at,
        content=f.content,
        truncated=f.truncated,
        binary=f.binary,
    )


@router.get("/info")
async def get_workspace_info(
    _current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> dict:
    """Lightweight info about the active backend (used by the workspace UI)."""
    backend = active_backend()
    info: dict = {
        "backend": backend,
        "workdir": (
            settings.DEEP_AGENT_SANDBOX_WORKDIR if backend == "modal" else None
        ),
    }
    if backend == "modal":
        # Don't force-create a sandbox on info — only report id if one exists.
        from app.ai.backend.sandbox import get_sandbox

        sb = get_sandbox()
        info["sandbox_id"] = getattr(sb, "object_id", None) if sb else None
    return info


@router.post("/sandbox/reset")
async def reset_workspace_sandbox(
    _current_user: Annotated[UserResponse, Depends(RequireAdmin)],
) -> dict:
    """Terminate and rebuild the Modal sandbox; rebuild the agent on next call.

    Returns 409 when ``DEEP_AGENT_BACKEND`` is not ``"modal"``.
    """
    backend = active_backend()
    if backend != "modal":
        raise HTTPException(
            status_code=409,
            detail=f"Sandbox reset only applies to backend='modal'; current is '{backend}'",
        )

    from app.ai.agents.deep_agent import reset_deep_agent
    from app.ai.backend.sandbox import reset_sandbox

    new_id = reset_sandbox()
    reset_deep_agent()
    if new_id is None:
        raise HTTPException(
            status_code=502,
            detail="Failed to rebuild sandbox; see server logs.",
        )
    return {"sandbox_id": new_id}
