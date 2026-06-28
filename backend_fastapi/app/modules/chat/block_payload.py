"""Typed payloads per BlockType — validated on write, stored as JSONB."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from app.modules.chat.model import BlockType

if TYPE_CHECKING:
    from app.modules.chat.model import MessageRole

ContentFormat = Literal["plain", "markdown"]


class TextBlockPayload(BaseModel):
    text: str = Field(..., min_length=1)
    format: ContentFormat = "plain"


class CodeBlockPayload(BaseModel):
    language: str = Field(default="", max_length=64)
    code: str = Field(..., min_length=1)


class TableBlockPayload(BaseModel):
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ChartBlockPayload(BaseModel):
    chart_type: str = Field(default="bar", max_length=32)
    spec: dict[str, Any] = Field(default_factory=dict)


class LinkBlockPayload(BaseModel):
    url: str = Field(..., min_length=1)
    label: str = Field(default="")


class FileBlockPayload(BaseModel):
    path: str = Field(..., min_length=1)
    name: str = Field(default="")
    mime_type: str = Field(default="")


class OtherBlockPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class ToolCallBlockPayload(BaseModel):
    id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    status: Literal["running", "complete", "error"] = "complete"
    result: str | None = None
    started_at: int | None = None
    completed_at: int | None = None


class SubagentBlockPayload(BaseModel):
    id: str = Field(..., min_length=1)
    subagent_type: str = Field(default="agent", max_length=128)
    description: str = Field(default="")
    status: Literal["running", "complete", "error"] = "complete"
    content: str = Field(default="")
    result: str | None = None
    started_at: int | None = None
    completed_at: int | None = None


_PAYLOAD_MODEL: dict[BlockType, type[BaseModel]] = {
    BlockType.TEXT: TextBlockPayload,
    BlockType.TOOL_CALL: ToolCallBlockPayload,
    BlockType.SUBAGENT: SubagentBlockPayload,
    BlockType.CODE: CodeBlockPayload,
    BlockType.TABLE: TableBlockPayload,
    BlockType.CHART: ChartBlockPayload,
    BlockType.LINK: LinkBlockPayload,
    BlockType.FILE: FileBlockPayload,
    BlockType.OTHER: OtherBlockPayload,
}


def validate_block_payload(block_type: BlockType, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a block payload for the given type."""
    model = _PAYLOAD_MODEL.get(block_type)
    if model is None:
        raise ValueError(f"Unknown block type: {block_type}")
    return model.model_validate(payload).model_dump()


def default_format_for_role(role: MessageRole) -> ContentFormat:
    from app.modules.chat.model import MessageRole

    return "markdown" if role == MessageRole.ASSISTANT else "plain"


def text_from_payload(block_type: BlockType, payload: dict[str, Any]) -> str:
    """Extract display text from a validated payload."""
    if block_type == BlockType.TEXT:
        return TextBlockPayload.model_validate(payload).text
    if block_type == BlockType.CODE:
        return CodeBlockPayload.model_validate(payload).code
    if block_type == BlockType.TABLE:
        p = TableBlockPayload.model_validate(payload)
        if not p.rows:
            return ""
        lines = [" | ".join(p.headers)] if p.headers else []
        lines.extend(" | ".join(row) for row in p.rows)
        return "\n".join(lines)
    if block_type == BlockType.LINK:
        p = LinkBlockPayload.model_validate(payload)
        return p.label or p.url
    if block_type == BlockType.FILE:
        p = FileBlockPayload.model_validate(payload)
        return p.name or p.path
    return ""


def format_from_payload(block_type: BlockType, payload: dict[str, Any]) -> ContentFormat:
    """Return render format — only TEXT blocks carry format; others default to plain."""
    if block_type == BlockType.TEXT:
        return TextBlockPayload.model_validate(payload).format
    return "plain"
