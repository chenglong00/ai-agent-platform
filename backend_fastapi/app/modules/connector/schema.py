"""Connector API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectorCatalogItem(BaseModel):
    id: str
    name: str
    description: str
    category: str
    mcp_url: str
    oauth_scopes: list[str]
    docs_url: str


class UserConnectorSummary(BaseModel):
    id: UUID
    connector_id: str
    enabled: bool
    connected: bool
    account_email: str | None = None
    last_connected_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ConnectorStatusItem(BaseModel):
    catalog: ConnectorCatalogItem
    connection: UserConnectorSummary | None = None


class AuthorizeConnectorResponse(BaseModel):
    authorize_url: str


class UpdateConnectorRequest(BaseModel):
    enabled: bool = Field(...)


class ConnectorToolsResponse(BaseModel):
    connector_id: str
    tools: list[dict[str, str | None]]


class DisconnectConnectorResponse(BaseModel):
    connector_id: str
    disconnected: bool = True
