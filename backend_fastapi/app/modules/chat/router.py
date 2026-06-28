"""Chat API: conversations, message history, and streaming agent replies."""

from __future__ import annotations

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from google.auth.exceptions import DefaultCredentialsError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security.dependencies import get_db
from app.modules.auth.rbac import RequireUser
from app.modules.agent.service import agent_service
from app.modules.chat.model import BlockType, MessageRole
from app.modules.chat.schema import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageBlockResponse,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    UpdateConversationRequest,
)
from app.modules.chat.service import chat_service
from app.modules.chat.browser_live import router as browser_live_router
from app.modules.knowledge_base.access import build_user_access_context
from app.modules.user.schema import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()
router.include_router(browser_live_router)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _message_response(message) -> MessageResponse:
    blocks = chat_service.message_blocks_response(message)
    return MessageResponse(
        id=message.id,
        role=message.role,
        text=chat_service.message_plain_text(message),
        created_at=message.created_at,
        content_format=chat_service.message_content_format(message),
        blocks=blocks,
    )


def _block_specs_from_done(chunk: dict) -> list[tuple[BlockType, dict]] | None:
    raw_specs = chunk.get("block_specs")
    if not raw_specs:
        return None
    specs: list[tuple[BlockType, dict]] = []
    for item in raw_specs:
        block_type = BlockType(item["block_type"])
        specs.append((block_type, item["payload"]))
    return specs


async def _require_owned_conversation(
    session: AsyncSession,
    conversation_id: UUID,
    current_user: UserResponse,
):
    conv = await chat_service.get_conversation(session, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return conv


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    body: CreateConversationRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> ConversationResponse:
    conv = await chat_service.create_conversation(
        session,
        current_user.id,
        body.name,
        description=body.description,
    )
    return ConversationResponse.model_validate(conv)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
    limit: Annotated[int, Query(ge=1, le=100)] = 15,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConversationListResponse:
    rows, has_more = await chat_service.list_conversations(
        session,
        current_user.id,
        limit=limit,
        offset=offset,
    )
    return ConversationListResponse(
        items=[ConversationResponse.model_validate(c) for c in rows],
        has_more=has_more,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> ConversationResponse:
    conv = await _require_owned_conversation(session, conversation_id, current_user)
    return ConversationResponse.model_validate(conv)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def list_conversation_messages(
    conversation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> list[MessageResponse]:
    await _require_owned_conversation(session, conversation_id, current_user)
    rows = await chat_service.list_messages(session, conversation_id)
    return [_message_response(m) for m in rows]


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    body: UpdateConversationRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> ConversationResponse:
    conv = await _require_owned_conversation(session, conversation_id, current_user)
    updated = await chat_service.update_conversation(session, conv, name=body.name)
    return ConversationResponse.model_validate(updated)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
)
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> SendMessageResponse:
    await _require_owned_conversation(session, conversation_id, current_user)

    history_rows = await chat_service.list_messages(session, conversation_id)
    conversation_history = [
        (m.role.value, chat_service.message_plain_text(m))
        for m in history_rows
    ]
    user_msg = await chat_service.add_message(
        session,
        conversation_id,
        MessageRole.USER,
        text=body.text,
    )
    kb_ctx = await build_user_access_context(session, current_user)

    try:
        assistant_text, pending_tool_calls = await agent_service.reply(
            body.agent_type,
            body.text,
            user_id=current_user.id,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            user_role=kb_ctx.role.value,
            group_ids=list(kb_ctx.group_ids),
        )
    except DefaultCredentialsError:
        logger.exception(
            "assistant_reply_failed_no_gcp_credentials conversation_id=%s",
            conversation_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Google Cloud credentials are missing for the assistant.",
        ) from None
    except Exception:
        logger.exception("assistant_reply_failed conversation_id=%s", conversation_id)
        raise HTTPException(
            status_code=503,
            detail="Assistant temporarily unavailable",
        ) from None

    asst_msg = await chat_service.add_message(
        session,
        conversation_id,
        MessageRole.ASSISTANT,
        text=assistant_text,
    )
    return SendMessageResponse(
        user_message_id=user_msg.id,
        assistant_message_id=asst_msg.id,
        assistant_text=assistant_text,
        assistant_content_format=chat_service.message_content_format(asst_msg),
        interrupted=bool(pending_tool_calls),
        pending_tool_calls=pending_tool_calls,
    )


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> StreamingResponse:
    """Stream the assistant reply as SSE. Persists both messages when done."""
    await _require_owned_conversation(session, conversation_id, current_user)

    history_rows = await chat_service.list_messages(session, conversation_id)
    conversation_history = [
        (m.role.value, chat_service.message_plain_text(m))
        for m in history_rows
    ]
    user_msg = await chat_service.add_message(
        session,
        conversation_id,
        MessageRole.USER,
        text=body.text,
    )
    kb_ctx = await build_user_access_context(session, current_user)

    async def generate():
        yield _sse({"type": "start", "user_message_id": str(user_msg.id)})

        full_text = ""
        interrupted = False
        block_specs: list[tuple[BlockType, dict]] | None = None
        try:
            async for chunk in agent_service.stream_reply(
                body.agent_type,
                body.text,
                user_id=current_user.id,
                conversation_id=conversation_id,
                conversation_history=conversation_history,
                user_role=kb_ctx.role.value,
                group_ids=list(kb_ctx.group_ids),
            ):
                if chunk["type"] == "done":
                    full_text = chunk.get("full_text", "")
                    interrupted = chunk.get("interrupted", False)
                    block_specs = _block_specs_from_done(chunk)
                else:
                    yield _sse(chunk)
        except DefaultCredentialsError:
            logger.exception(
                "stream_reply_failed_no_gcp_credentials conversation_id=%s",
                conversation_id,
            )
            yield _sse({"type": "error", "message": "Google Cloud credentials are missing."})
            return
        except Exception as exc:
            logger.exception("stream_reply_error conversation_id=%s", conversation_id)
            yield _sse({"type": "error", "message": str(exc)})
            return

        if not interrupted and not full_text:
            full_text = (
                "I completed the request but couldn't produce a visible reply. "
                "Please try again."
            )

        if block_specs:
            asst_msg = await chat_service.add_message(
                session,
                conversation_id,
                MessageRole.ASSISTANT,
                text="",
                block_specs=block_specs,
            )
            assistant_blocks = [
                block.model_dump()
                for block in chat_service.block_specs_to_response(block_specs)
            ]
        else:
            asst_msg = await chat_service.add_message(
                session,
                conversation_id,
                MessageRole.ASSISTANT,
                text=full_text,
            )
            assistant_blocks = [
                block.model_dump()
                for block in chat_service.message_blocks_response(asst_msg)
            ]
        yield _sse({
            "type": "saved",
            "assistant_message_id": str(asst_msg.id),
            "assistant_text": full_text,
            "assistant_blocks": assistant_blocks,
            "interrupted": interrupted,
        })
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
