"""Chat API request/response schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.agent import AgentType
from app.models.chat import MessageRole


class CreateConversationRequest(BaseModel):
    name: str = Field(default="New chat", max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class UpdateConversationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name cannot be blank")
        return s


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    has_more: bool


class MessageResponse(BaseModel):
    """One chat line for the UI.

    ``text`` is the full body: for ``content_format == "markdown"`` (typical assistant
    replies), render with a markdown component (e.g. Streamdown / ``MessageResponse``).
    User messages are usually ``plain`` unless you store markdown from the client.
    """

    id: UUID
    role: MessageRole
    text: str = Field(
        ...,
        description="Message body: markdown or plain text per content_format.",
    )
    created_at: datetime = Field(
        ...,
        description="Server time when the message was stored (ISO-8601 in JSON).",
    )
    content_format: Literal["markdown", "plain"] = Field(
        ...,
        description='How to render ``text``: "markdown" for rich text (lists, code, '
        'tables); "plain" for escaped text or simple bubbles.',
    )


class SendMessageRequest(BaseModel):
    text: str = Field(..., min_length=1)
    agent_type: AgentType | None = None


class PendingToolCall(BaseModel):
    """Describes a tool call that is paused waiting for human approval."""

    tool_name: str
    args: dict
    description: str


class SendMessageResponse(BaseModel):
    """Result of one send + model reply; aligns with ``MessageResponse`` for the assistant line."""

    user_message_id: UUID
    assistant_message_id: UUID
    assistant_text: str = Field(
        ...,
        description="Assistant reply body; treat as markdown (same as MessageResponse with content_format=markdown).",
    )
    assistant_content_format: Literal["markdown", "plain"] = Field(
        default="markdown",
        description="Render assistant_text as markdown unless you override for a plain model.",
    )
    interrupted: bool = Field(
        default=False,
        description="True when the agent is paused waiting for human approval of a tool call.",
    )
    pending_tool_calls: list[PendingToolCall] = Field(
        default_factory=list,
        description="Tool calls awaiting approval when interrupted=true.",
    )
