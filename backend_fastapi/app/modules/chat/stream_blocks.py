"""Collect streamed turn events into ordered message block specs."""

from __future__ import annotations

from typing import Any, Literal

from app.modules.chat.block_payload import ContentFormat
from app.modules.chat.model import BlockType

SegmentKind = Literal["tool_call", "subagent"]


class TurnBlockCollector:
    """Accumulates tool/subagent SSE events into persistable block order."""

    def __init__(self) -> None:
        self._order: list[tuple[SegmentKind, str]] = []
        self._seen: set[tuple[SegmentKind, str]] = set()
        self._tools: dict[str, dict[str, Any]] = {}
        self._subagents: dict[str, dict[str, Any]] = {}

    def observe(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "tool_call_start":
            call_id = str(event["id"])
            self._note("tool_call", call_id)
            self._tools[call_id] = {
                "id": call_id,
                "tool_name": event.get("tool_name", ""),
                "args": event.get("args") or {},
                "status": "running",
                "started_at": event.get("started_at"),
            }
        elif event_type == "tool_call_end":
            call_id = str(event["id"])
            self._note("tool_call", call_id)
            existing = self._tools.get(call_id, {"id": call_id})
            self._tools[call_id] = {
                **existing,
                "tool_name": event.get("tool_name", existing.get("tool_name", "")),
                "status": event.get("status", "complete"),
                "result": event.get("result"),
                "completed_at": event.get("completed_at"),
            }
        elif event_type == "subagent_start":
            sa_id = str(event["id"])
            self._note("subagent", sa_id)
            self._subagents[sa_id] = {
                "id": sa_id,
                "subagent_type": event.get("subagent_type", "agent"),
                "description": event.get("description", ""),
                "status": "running",
                "content": "",
                "started_at": event.get("started_at"),
            }
        elif event_type == "subagent_token":
            sa_id = str(event["id"])
            sa = self._subagents.get(sa_id)
            if sa is not None:
                sa["content"] = sa.get("content", "") + str(event.get("content", ""))
        elif event_type == "subagent_done":
            sa_id = str(event["id"])
            self._note("subagent", sa_id)
            existing = self._subagents.get(sa_id, {"id": sa_id, "content": ""})
            self._subagents[sa_id] = {
                **existing,
                "status": event.get("status", "complete"),
                "result": event.get("result"),
                "completed_at": event.get("completed_at"),
            }

    def _note(self, kind: SegmentKind, segment_id: str) -> None:
        key = (kind, segment_id)
        if key in self._seen:
            return
        self._seen.add(key)
        self._order.append(key)

    def to_block_specs(
        self,
        text: str,
        *,
        content_format: ContentFormat = "markdown",
    ) -> list[tuple[BlockType, dict[str, Any]]]:
        specs: list[tuple[BlockType, dict[str, Any]]] = []
        for kind, segment_id in self._order:
            if kind == "tool_call":
                payload = self._tools.get(segment_id)
                if payload:
                    specs.append((BlockType.TOOL_CALL, dict(payload)))
            elif kind == "subagent":
                payload = self._subagents.get(segment_id)
                if payload:
                    specs.append((BlockType.SUBAGENT, dict(payload)))
        if text.strip():
            specs.append(
                (BlockType.TEXT, {"text": text, "format": content_format}),
            )
        return specs
