"""Persistence for conversations, messages, and message blocks."""

from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.chat import BlockType, Conversation, Message, MessageBlock, MessageRole
from app.utils.datetime import now_utc


class ChatService:
    """Stateless chat persistence. Pass ``AsyncSession`` per call."""

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
        block_specs: list[tuple[BlockType, str]] | None = None,
        text: str | None = None,
    ) -> Message:
        """Insert a message and its blocks in one commit.

        ``Message`` has no top-level ``content`` column — payload lives in ``MessageBlock`` rows.

        **Does commit save blocks automatically?** Yes, if you attach blocks through
        ``message.blocks.append(...)`` and ``session.add(message)`` only. Parent
        ``Message.blocks`` uses ``cascade="all, delete-orphan"``, which includes
        **save-update**, so the ORM INSERTs the message first, then each block with
        the correct ``message_id``. Do **not** set ``message_id`` yourself before flush;
        do **not** ``session.add`` each block unless you prefer (redundant here).

        Provide either ``text=`` (single TEXT block) or ``block_specs=`` as
        ``[(BlockType, content_str), ...]``.
        """
        message = Message(conversation_id=conversation_id, role=role)

        if block_specs:
            for block_type, content in block_specs:
                message.blocks.append(
                    MessageBlock(block_type=block_type, content=content),
                )
        elif text is not None:
            message.blocks.append(MessageBlock(block_type=BlockType.TEXT, content=text))
        else:
            raise ValueError("Provide text= or block_specs=[(BlockType, str), ...]")

        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message

    def message_plain_text(self, message: Message) -> str:
        """Flatten block payloads into one string (API / display), ordered by block id."""
        blocks = sorted(message.blocks, key=lambda b: b.id)
        return "\n".join(b.content for b in blocks)

    async def list_messages(
        self,
        session: AsyncSession,
        conversation_id: UUID,
    ) -> list[Message]:
        """Messages in creation order, with blocks preloaded."""
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .options(selectinload(Message.blocks))
            .order_by(Message.created_at.asc())
        )
        result = await session.exec(statement)
        return list(result.all())

    async def get_conversation(
        self, session: AsyncSession, conversation_id: UUID
    ) -> Conversation | None:
        """Load a conversation by primary key, or ``None`` if missing."""
        return await session.get(Conversation, conversation_id)

    async def list_conversations(
        self,
        session: AsyncSession,
        owner_id: UUID,
        *,
        limit: int = 15,
        offset: int = 0,
    ) -> tuple[list[Conversation], bool]:
        """List conversations for a user, most recently updated first.

        Returns ``(page, has_more)`` using a limit+1 probe (no separate count).
        """
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
        self, session: AsyncSession, conversation_id: UUID
    ) -> bool:
        """Delete a conversation (cascades to messages/blocks per ORM config)."""
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            return False
        await session.delete(conversation)
        await session.commit()
        return True


chat_service = ChatService()
