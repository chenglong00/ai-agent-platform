"""Chat API: conversations, message history, and turns (persist + LLM reply)."""

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from google.auth.exceptions import DefaultCredentialsError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.dependency import RequireUser, get_db
from app.models.chat import MessageRole
from app.schemas.chat import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    UpdateConversationRequest,
)
from app.schemas.user import UserResponse
from app.services.agent_service import agent_service
from app.services.chat_service import chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def get_conversation(
    conversation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> ConversationResponse:
    conv = await chat_service.get_conversation(session, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
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
    conv = await chat_service.get_conversation(session, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    rows = await chat_service.list_messages(session, conversation_id)
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            text=chat_service.message_plain_text(m),
            created_at=m.created_at,
            content_format="markdown"
            if m.role == MessageRole.ASSISTANT
            else "plain",
        )
        for m in rows
    ]

@router.put(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def update_conversation(
    conversation_id: UUID,
    body: UpdateConversationRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> ConversationResponse:
    conv = await chat_service.get_conversation(session, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    updated = await chat_service.update_conversation(
        session, conv, name=body.name
    )
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
    """Store the user message, run the assistant, store the reply, return both ids and reply text."""
    conv = await chat_service.get_conversation(session, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

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
    try:
        assistant_text, pending_tool_calls = await agent_service.reply(
            body.agent_type,
            body.text,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
        )
    except DefaultCredentialsError:
        logger.exception(
            "assistant_reply_failed_no_gcp_credentials conversation_id=%s",
            conversation_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Cloud credentials are missing. In Docker, ensure the service account "
                "JSON is mounted (see docker-compose.yml: GCP_SERVICE_ACCOUNT_JSON / default "
                "path under backend_fastapi/secrets/)."
            ),
        ) from None
    except Exception:
        logger.exception(
            "assistant_reply_failed conversation_id=%s",
            conversation_id,
        )
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
    logger.debug(
        "assistant_message_persisted conversation_id=%s user_message_id=%s assistant_message_id=%s assistant_chars=%s",
        conversation_id,
        user_msg.id,
        asst_msg.id,
        len(assistant_text),
    )
    return SendMessageResponse(
        user_message_id=user_msg.id,
        assistant_message_id=asst_msg.id,
        assistant_text=assistant_text,
        assistant_content_format="markdown",
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
    conv = await chat_service.get_conversation(session, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    history_rows = await chat_service.list_messages(session, conversation_id)
    conversation_history = [
        (m.role.value, chat_service.message_plain_text(m)) for m in history_rows
    ]
    user_msg = await chat_service.add_message(
        session, conversation_id, MessageRole.USER, text=body.text
    )

    async def generate():
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data)}\n\n"

        yield sse({"type": "start", "user_message_id": str(user_msg.id)})

        full_text = ""
        interrupted = False
        try:
            async for chunk in agent_service.stream_reply(
                body.agent_type,
                body.text,
                conversation_id=conversation_id,
                conversation_history=conversation_history,
            ):
                if chunk["type"] == "done":
                    full_text = chunk.get("full_text", "")
                    interrupted = chunk.get("interrupted", False)
                else:
                    yield sse(chunk)
        except Exception as exc:
            logger.exception("stream_reply_error conversation_id=%s", conversation_id)
            yield sse({"type": "error", "message": str(exc)})

        if not interrupted and not full_text:
            full_text = "I completed the request but couldn't produce a visible reply. Please try again."

        asst_msg = await chat_service.add_message(
            session, conversation_id, MessageRole.ASSISTANT, text=full_text
        )
        yield sse({
            "type": "saved",
            "assistant_message_id": str(asst_msg.id),
            "assistant_text": full_text,
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
