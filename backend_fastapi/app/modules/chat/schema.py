"""Chat API request/response schemas."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.agent.model import AgentType
from app.modules.chat.model import MessageRole


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


class MessageBlockResponse(BaseModel):
    type: str
    position: int
    payload: dict[str, Any]


class MessageResponse(BaseModel):
    id: UUID
    role: MessageRole
    text: str
    created_at: datetime
    content_format: Literal["markdown", "plain"]
    blocks: list[MessageBlockResponse] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    text: str = Field(..., min_length=1)
    agent_type: AgentType | None = None


class PendingToolCall(BaseModel):
    tool_name: str
    args: dict[str, Any]
    description: str


class SendMessageResponse(BaseModel):
    user_message_id: UUID
    assistant_message_id: UUID
    assistant_text: str
    assistant_content_format: Literal["markdown", "plain"] = "markdown"
    interrupted: bool = False
    pending_tool_calls: list[PendingToolCall] = Field(default_factory=list)
