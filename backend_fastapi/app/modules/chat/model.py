"""Chat domain: conversations, messages, and message blocks."""

from __future__ import annotations

import enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from app.utils.datetime import datetime, now_utc


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class BlockType(str, enum.Enum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    SUBAGENT = "subagent"
    TABLE = "table"
    CODE = "code"
    CHART = "chart"
    LINK = "link"
    FILE = "file"
    OTHER = "other"


class MessageBlock(SQLModel, table=True):
    __tablename__ = "message_blocks"
    __table_args__ = (
        UniqueConstraint("message_id", "position", name="uq_message_blocks_message_id_position"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    message_id: UUID = Field(foreign_key="messages.id", nullable=False, index=True)
    block_type: BlockType = Field(nullable=False, max_length=20)
    position: int = Field(default=0, nullable=False)
    payload: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))

    message: Optional["Message"] = Relationship(
        sa_relationship=relationship(
            "Message",
            back_populates="blocks",
        ),
    )


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(foreign_key="conversations.id", nullable=False, index=True)
    role: MessageRole = Field(nullable=False, max_length=9)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)

    conversation: Optional["Conversation"] = Relationship(
        sa_relationship=relationship(
            "Conversation",
            back_populates="messages",
        ),
    )
    blocks: list["MessageBlock"] = Relationship(
        sa_relationship=relationship(
            "MessageBlock",
            back_populates="message",
            cascade="all, delete-orphan",
            order_by="MessageBlock.position",
        ),
    )


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    name: str = Field(nullable=False, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)

    owner: Optional["User"] = Relationship(
        sa_relationship=relationship(
            "User",
            back_populates="conversations",
        ),
    )
    messages: list["Message"] = Relationship(
        sa_relationship=relationship(
            "Message",
            back_populates="conversation",
            cascade="all, delete-orphan",
            order_by="Message.created_at",
        ),
    )


from app.modules.user.model import User  # noqa: E402
