"""Catalog of official remote MCP connectors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConnectorDefinition:
    id: str
    name: str
    description: str
    category: str
    mcp_url: str
    oauth_scopes: tuple[str, ...]
    docs_url: str


CONNECTOR_CATALOG: dict[str, ConnectorDefinition] = {
    "google_calendar": ConnectorDefinition(
        id="google_calendar",
        name="Google Calendar",
        description="List calendars, read and manage events via Google's official Calendar MCP server.",
        category="Google Workspace",
        mcp_url="https://calendarmcp.googleapis.com/mcp/v1",
        oauth_scopes=(
            "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
            "https://www.googleapis.com/auth/calendar.events.freebusy",
            "https://www.googleapis.com/auth/calendar.events.readonly",
            "https://www.googleapis.com/auth/calendar.events",
        ),
        docs_url="https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server",
    ),
    "google_drive": ConnectorDefinition(
        id="google_drive",
        name="Google Drive",
        description="Search, read, and create files via Google's official Drive MCP server.",
        category="Google Workspace",
        mcp_url="https://drivemcp.googleapis.com/mcp/v1",
        oauth_scopes=(
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.file",
        ),
        docs_url="https://developers.google.com/workspace/drive/api/guides/configure-mcp-server",
    ),
    "google_gmail": ConnectorDefinition(
        id="google_gmail",
        name="Gmail",
        description="Read and send email via Google's official Gmail MCP server.",
        category="Google Workspace",
        mcp_url="https://gmailmcp.googleapis.com/mcp/v1",
        oauth_scopes=(
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
        ),
        docs_url="https://developers.google.com/workspace/gmail/api/guides/configure-mcp-server",
    ),
}


def get_connector_definition(connector_id: str) -> ConnectorDefinition | None:
    return CONNECTOR_CATALOG.get(connector_id)


def list_connector_definitions() -> list[ConnectorDefinition]:
    return list(CONNECTOR_CATALOG.values())
