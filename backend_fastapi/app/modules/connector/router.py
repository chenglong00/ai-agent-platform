"""Connector management and OAuth callback routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security.dependencies import get_db
from app.modules.auth.rbac import RequireUser
from app.modules.connector.oauth_flow import build_connector_success_redirect
from app.modules.connector.schema import (
    AuthorizeConnectorResponse,
    ConnectorStatusItem,
    ConnectorToolsResponse,
    DisconnectConnectorResponse,
    UpdateConnectorRequest,
    UserConnectorSummary,
)
from app.modules.connector.service import connector_service
from app.modules.user.schema import UserResponse

router = APIRouter()


@router.get("", response_model=list[ConnectorStatusItem])
async def list_connectors(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> list[ConnectorStatusItem]:
    return await connector_service.list_status(session, current_user.id)


@router.post("/{connector_id}/authorize", response_model=AuthorizeConnectorResponse)
async def authorize_connector(
    connector_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> AuthorizeConnectorResponse:
    return await connector_service.begin_oauth(session, current_user.id, connector_id)


@router.get("/oauth/callback")
async def connector_oauth_callback(
    session: Annotated[AsyncSession, Depends(get_db)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
):
    if error:
        redirect = build_connector_success_redirect(connector_id="", status="error")
        return RedirectResponse(url=f"{redirect}&message={error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state")

    summary = await connector_service.complete_oauth(session, code=code, state=state)
    redirect = build_connector_success_redirect(connector_id=summary.connector_id, status="connected")
    return RedirectResponse(url=redirect)


@router.patch("/{connector_id}", response_model=UserConnectorSummary)
async def update_connector(
    connector_id: str,
    body: UpdateConnectorRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> UserConnectorSummary:
    return await connector_service.update_enabled(
        session,
        current_user.id,
        connector_id,
        body.enabled,
    )


@router.delete("/{connector_id}", response_model=DisconnectConnectorResponse)
async def disconnect_connector(
    connector_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> DisconnectConnectorResponse:
    await connector_service.disconnect(session, current_user.id, connector_id)
    return DisconnectConnectorResponse(connector_id=connector_id)


@router.get("/{connector_id}/tools", response_model=ConnectorToolsResponse)
async def list_connector_tools(
    connector_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> ConnectorToolsResponse:
    return await connector_service.list_mcp_tools(session, current_user.id, connector_id)
