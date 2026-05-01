"""Chat domain: conversations, messages, and UI-oriented message blocks."""

from __future__ import annotations

import enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, Text
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from app.models.user import User
from app.utils.datetime import datetime, now_utc


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class BlockType(str, enum.Enum):
    """Kind of rendered segment (maps well to Slack-style / rich UI blocks)."""

    TEXT = "text"
    TABLE = "table"
    CODE = "code"
    CHART = "chart"
    LINK = "link"
    FILE = "file"
    OTHER = "other"


class MessageBlock(SQLModel, table=True):
    """One UI segment inside a message (text, table, chart, etc.)."""

    __tablename__ = "message_blocks"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    message_id: UUID = Field(foreign_key="messages.id", nullable=False, index=True)
    block_type: BlockType = Field(nullable=False)
    content: str = Field(sa_column=Column(Text, nullable=False))

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
    role: MessageRole = Field(nullable=False)
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
            order_by="MessageBlock.id",
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

    owner: Optional[User] = Relationship(
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
