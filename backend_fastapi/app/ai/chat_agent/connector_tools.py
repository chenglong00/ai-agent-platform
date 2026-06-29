"""LangChain tools that proxy to user-connected MCP servers."""

from __future__ import annotations

import json
import logging
from uuid import UUID

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from sqlmodel import select

from app.ai.chat_agent.run_context import get_user_id_from_run
from app.core.config import settings
from app.core.db.postgres import get_async_session_factory
from app.modules.connector.auth_manager import connector_auth_manager
from app.modules.connector.catalog import get_connector_definition
from app.modules.connector.mcp_client import McpClientError, RemoteMcpClient
from app.modules.connector.model import UserConnector

logger = logging.getLogger(__name__)


def _parse_tool_arguments(raw: object) -> dict[str, object]:
    """Accept JSON object strings (including double-encoded) from the LLM."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("arguments_json must be a JSON object string.")

    parsed: object = json.loads(raw)
    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    if not isinstance(parsed, dict):
        raise ValueError("arguments_json must decode to a JSON object.")
    return parsed


async def _enabled_connectors(user_id: UUID) -> list[UserConnector]:
    factory = get_async_session_factory()
    async with factory() as session:
        statement = (
            select(UserConnector)
            .where(UserConnector.user_id == user_id, UserConnector.enabled.is_(True))
            .order_by(UserConnector.connector_id)
        )
        return list((await session.exec(statement)).all())


@tool
async def list_connected_connectors(runtime: ToolRuntime) -> str:
    """List enterprise connectors the user has connected and enabled (Google Calendar, Drive, Gmail)."""
    if not settings.CONNECTORS_ENABLED:
        return "Connectors are disabled."

    try:
        user_id = UUID(get_user_id_from_run(runtime))
        rows = await _enabled_connectors(user_id)
        if not rows:
            return "No connected enterprise connectors. The user can connect services on the Connector page."

        lines: list[str] = []
        for row in rows:
            definition = get_connector_definition(row.connector_id)
            name = definition.name if definition else row.connector_id
            status = "connected" if row.access_token else "needs auth"
            lines.append(f"- {row.connector_id} ({name}): {status}")
        return "Connected connectors:\n" + "\n".join(lines)
    except Exception as exc:
        logger.exception("list_connected_connectors_failed")
        return f"Could not list connectors: {exc}"


@tool
async def call_connector_mcp_tool(
    connector_id: str,
    tool_name: str,
    arguments_json: str,
    runtime: ToolRuntime,
) -> str:
    """Call a tool on an official Google Workspace MCP server for the current user.

    connector_id: google_calendar | google_drive | google_gmail
    tool_name: MCP tool name from that server (e.g. list_events, search_files)
    arguments_json: JSON object string of tool arguments, e.g. {}
    """
    if not settings.CONNECTORS_ENABLED:
        return "Connectors are disabled."

    definition = get_connector_definition(connector_id.strip())
    if definition is None:
        return f"Unknown connector_id: {connector_id}"

    try:
        arguments = _parse_tool_arguments(arguments_json)
    except (json.JSONDecodeError, ValueError) as exc:
        return f"Invalid arguments_json: {exc}"

    try:
        user_id = UUID(get_user_id_from_run(runtime))
        factory = get_async_session_factory()
        async with factory() as session:
            access_token = await connector_auth_manager.get_valid_access_token(
                session,
                user_id=user_id,
                connector_id=definition.id,
            )
            client = RemoteMcpClient(mcp_url=definition.mcp_url, access_token=access_token)
            result = await client.call_tool(tool_name, arguments)
        return json.dumps(result, default=str)[:12000]
    except McpClientError as exc:
        logger.warning(
            "call_connector_mcp_tool_mcp_error connector=%s tool=%s error=%s",
            connector_id,
            tool_name,
            exc,
        )
        return f"MCP tool error: {exc}"
    except Exception as exc:
        logger.exception("call_connector_mcp_tool_failed connector=%s tool=%s", connector_id, tool_name)
        return f"MCP tool call failed: {exc}"
