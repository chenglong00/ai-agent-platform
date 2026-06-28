"""Persistence for conversations, messages, and message blocks."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.chat.block_payload import (
    ContentFormat,
    default_format_for_role,
    format_from_payload,
    text_from_payload,
    validate_block_payload,
)
from app.modules.chat.model import BlockType, Conversation, Message, MessageBlock, MessageRole
from app.modules.chat.schema import MessageBlockResponse
from app.utils.datetime import now_utc


class ChatService:
    """Stateless chat persistence. Pass ``AsyncSession`` per call."""

    @staticmethod
    def block_text(block: MessageBlock) -> str:
        return text_from_payload(block.block_type, block.payload)

    @staticmethod
    def block_format(block: MessageBlock) -> ContentFormat:
        return format_from_payload(block.block_type, block.payload)

    def message_plain_text(self, message: Message) -> str:
        blocks = sorted(message.blocks, key=lambda b: (b.position, b.id))
        parts = [self.block_text(b) for b in blocks if self.block_text(b)]
        return "\n".join(parts)

    def message_content_format(self, message: Message) -> ContentFormat:
        """Format comes from block payloads; markdown if any text block uses it."""
        blocks = sorted(message.blocks, key=lambda b: (b.position, b.id))
        for block in blocks:
            if self.block_format(block) == "markdown":
                return "markdown"
        if blocks:
            return self.block_format(blocks[0])
        return default_format_for_role(message.role)

    @staticmethod
    def message_blocks_response(message: Message) -> list[MessageBlockResponse]:
        blocks = sorted(message.blocks, key=lambda b: (b.position, str(b.id)))
        return [
            MessageBlockResponse(
                type=block.block_type.value,
                position=block.position,
                payload=block.payload,
            )
            for block in blocks
        ]

    @staticmethod
    def block_specs_to_response(
        block_specs: list[tuple[BlockType, dict]],
    ) -> list[MessageBlockResponse]:
        return [
            MessageBlockResponse(
                type=block_type.value,
                position=position,
                payload=payload,
            )
            for position, (block_type, payload) in enumerate(block_specs)
        ]

    def add_blocks(
        self,
        message: Message,
        block_specs: list[tuple[BlockType, dict]],
    ) -> None:
        for position, (block_type, payload) in enumerate(block_specs):
            validated = validate_block_payload(block_type, payload)
            message.blocks.append(
                MessageBlock(
                    block_type=block_type,
                    position=position,
                    payload=validated,
                ),
            )

    async def create_conversation(
        self,
        session: AsyncSession,
        owner_id: UUID,
        name: str,
        description: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            owner_id=owner_id,
            name=name,
            description=description,
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

    async def add_message(
        self,
        session: AsyncSession,
        conversation_id: UUID,
        role: MessageRole,
        *,
        text: str,
        content_format: ContentFormat | None = None,
        block_specs: list[tuple[BlockType, dict]] | None = None,
    ) -> Message:
        message = Message(conversation_id=conversation_id, role=role)

        if block_specs:
            self.add_blocks(message, block_specs)
        else:
            fmt = content_format or default_format_for_role(role)
            self.add_blocks(
                message,
                [(BlockType.TEXT, {"text": text, "format": fmt})],
            )

        session.add(message)

        conversation = await session.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.updated_at = now_utc()
            session.add(conversation)

        await session.commit()
        statement = (
            select(Message)
            .where(Message.id == message.id)
            .options(selectinload(Message.blocks))
        )
        result = await session.exec(statement)
        return result.one()

    async def list_messages(
        self,
        session: AsyncSession,
        conversation_id: UUID,
    ) -> list[Message]:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .options(selectinload(Message.blocks))
            .order_by(Message.created_at.asc())
        )
        result = await session.exec(statement)
        return list(result.all())

    async def get_conversation(
        self,
        session: AsyncSession,
        conversation_id: UUID,
    ) -> Conversation | None:
        return await session.get(Conversation, conversation_id)

    async def list_conversations(
        self,
        session: AsyncSession,
        owner_id: UUID,
        *,
        limit: int = 15,
        offset: int = 0,
    ) -> tuple[list[Conversation], bool]:
        page_limit = min(max(limit, 1), 100)
        take = page_limit + 1
        statement = (
            select(Conversation)
            .where(Conversation.owner_id == owner_id)
            .order_by(Conversation.updated_at.desc())
            .offset(max(offset, 0))
            .limit(take)
        )
        result = await session.exec(statement)
        rows = list(result.all())
        has_more = len(rows) > page_limit
        return rows[:page_limit], has_more

    async def update_conversation(
        self,
        session: AsyncSession,
        conversation: Conversation,
        *,
        name: str,
    ) -> Conversation:
        conversation.name = name
        conversation.updated_at = now_utc()
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

    async def delete_conversation(
        self,
        session: AsyncSession,
        conversation_id: UUID,
    ) -> bool:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            return False
        await session.delete(conversation)
        await session.commit()
        return True


chat_service = ChatService()
