"""HTTP client for official Google remote MCP servers."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RemoteMcpClient:
    """Minimal JSON-RPC client for streamable HTTP MCP endpoints."""

    def __init__(self, *, mcp_url: str, access_token: str) -> None:
        self._mcp_url = mcp_url.rstrip("/")
        self._access_token = access_token
        self._request_id = 0

    async def list_tools(self) -> list[dict[str, Any]]:
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
        payload = await self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        if "error" in payload:
            raise RuntimeError(str(payload["error"]))
        result = payload.get("result") or {}
        return result.get("content") or result

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._request_id,
        }
        if params is not None:
            body["params"] = params

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self._mcp_url, json=body, headers=headers)
            resp.raise_for_status()
            return _parse_mcp_response(resp)


def _parse_mcp_response(resp: httpx.Response) -> dict[str, Any]:
    content_type = resp.headers.get("content-type", "")
    text = resp.text.strip()
    if not text:
        raise RuntimeError("Empty MCP response")

    if "text/event-stream" in content_type or text.startswith("event:") or text.startswith("data:"):
        return _parse_sse_payload(text)

    payload = resp.json()
    if isinstance(payload, dict):
        return payload
    raise RuntimeError("Unexpected MCP response shape")


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
    raise RuntimeError("Could not parse MCP SSE response")
