"""HTTP client for official Google remote MCP servers."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class McpClientError(RuntimeError):
    """Raised when an MCP server returns an application-level error."""


class RemoteMcpClient:
    """Minimal JSON-RPC client for streamable HTTP MCP endpoints."""

    def __init__(self, *, mcp_url: str, access_token: str) -> None:
        self._mcp_url = mcp_url.rstrip("/")
        self._access_token = access_token
        self._request_id = 0
        self._initialized = False

    async def list_tools(self) -> list[dict[str, Any]]:
        await self._ensure_initialized()
        payload = await self._request("tools/list")
        result = payload.get("result") or {}
        tools = result.get("tools") or []
        return [
            {
                "name": tool.get("name"),
                "description": tool.get("description"),
            }
            for tool in tools
            if tool.get("name")
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        await self._ensure_initialized()
        clean_name = name.strip()
        clean_args = _normalize_google_arguments(arguments or {})
        payload = await self._request(
            "tools/call",
            {"name": clean_name, "arguments": clean_args},
        )
        return _unwrap_tool_result(payload)

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        init_payload = await self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ai-agent-platform", "version": "0.1.0"},
            },
        )
        if "error" in init_payload:
            raise McpClientError(f"MCP initialize failed: {init_payload['error']}")
        self._initialized = True
        try:
            await self._request("notifications/initialized")
        except McpClientError:
            # Some servers return 202 with an empty body for notifications.
            pass

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._request_id,
        }
        if params is not None:
            body["params"] = params

        try:
            encoded = json.dumps(body, default=str)
        except (TypeError, ValueError) as exc:
            raise McpClientError(f"MCP request is not JSON-serializable: {exc}") from exc

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self._mcp_url,
                content=encoded,
                headers=headers,
            )

        if resp.status_code >= 400:
            message = _extract_http_error(resp)
            logger.warning(
                "mcp_http_error method=%s status=%s body=%s",
                method,
                resp.status_code,
                message[:500],
            )
            raise McpClientError(message)

        return _parse_mcp_response(resp)


def _normalize_google_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Google MCP tools expect camelCase argument names (startTime, pageSize, ...)."""
    normalized: dict[str, Any] = {}
    for key, value in arguments.items():
        if not isinstance(key, str):
            raise McpClientError("Tool arguments must use string keys.")
        normalized[_to_camel_case(key) if "_" in key else key] = value
    return normalized


def _to_camel_case(key: str) -> str:
    if key.startswith("_"):
        return key
    parts = key.split("_")
    if len(parts) == 1:
        return key
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:] if part)


def _unwrap_tool_result(payload: dict[str, Any]) -> Any:
    if "error" in payload:
        raise McpClientError(str(payload["error"]))

    result = payload.get("result") or {}
    if result.get("isError"):
        message = _format_tool_content(result.get("content"))
        raise McpClientError(message or "MCP tool returned an error")

    content = result.get("content")
    if content is not None:
        return content
    return result


def _format_tool_content(content: Any) -> str:
    if not content:
        return ""
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _extract_http_error(resp: httpx.Response) -> str:
    text = resp.text.strip()
    if not text:
        return f"MCP HTTP {resp.status_code}"
    try:
        payload = resp.json()
    except json.JSONDecodeError:
        return f"MCP HTTP {resp.status_code}: {text[:500]}"
    if isinstance(payload, dict):
        if "error" in payload:
            err = payload["error"]
            if isinstance(err, dict):
                return str(err.get("message") or err)
            return str(err)
        if "result" in payload:
            return _format_tool_content((payload.get("result") or {}).get("content")) or text[:500]
    return text[:500]


def _parse_mcp_response(resp: httpx.Response) -> dict[str, Any]:
    content_type = resp.headers.get("content-type", "")
    text = resp.text.strip()
    if not text:
        if resp.status_code in {202, 204}:
            return {}
        raise McpClientError("Empty MCP response")

    if "text/event-stream" in content_type or text.startswith("event:") or text.startswith("data:"):
        return _parse_sse_payload(text)

    payload = resp.json()
    if isinstance(payload, dict):
        return payload
    raise McpClientError("Unexpected MCP response shape")


def _parse_sse_payload(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise McpClientError("Could not parse MCP SSE response")
