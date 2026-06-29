"""LangChain tools that delegate work to user-registered A2A subagents."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types.a2a_pb2 import Message, Role, SendMessageRequest, StreamResponse
from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from sqlmodel import select

from app.ai.chat_agent.run_context import get_user_id_from_run
from app.core.config import settings
from app.core.db.postgres import get_async_session_factory
from app.modules.subagent.a2a_client import card_skills
from app.modules.subagent.model import UserSubagent

logger = logging.getLogger(__name__)

_RESPONSE_MAX_CHARS = 12_000
_A2A_TIMEOUT_SECONDS = 90.0


async def _enabled_subagents(user_id: UUID) -> list[UserSubagent]:
    factory = get_async_session_factory()
    async with factory() as session:
        statement = (
            select(UserSubagent)
            .where(UserSubagent.user_id == user_id, UserSubagent.enabled.is_(True))
            .order_by(UserSubagent.name)
        )
        return list((await session.exec(statement)).all())


async def _resolve_subagent(user_id: UUID, subagent_ref: str) -> UserSubagent | None:
    ref = subagent_ref.strip()
    if not ref:
        return None

    factory = get_async_session_factory()
    async with factory() as session:
        try:
            subagent_id = UUID(ref)
        except ValueError:
            subagent_id = None

        if subagent_id is not None:
            row = await session.get(UserSubagent, subagent_id)
            if row is not None and row.user_id == user_id and row.enabled:
                return row

        statement = (
            select(UserSubagent)
            .where(UserSubagent.user_id == user_id, UserSubagent.enabled.is_(True))
            .order_by(UserSubagent.name)
        )
        rows = list((await session.exec(statement)).all())
        lower = ref.lower()
        for row in rows:
            if row.name.lower() == lower:
                return row
        for row in rows:
            if lower in row.name.lower():
                return row
    return None


def _format_skills(card: dict) -> str:
    skills = card_skills(card if isinstance(card, dict) else {})
    if not skills:
        return "none listed"
    return "; ".join(
        f"{item.get('id') or item.get('name')}: {item.get('description', '')}".strip(": ")
        for item in skills[:8]
    )


def _message_text(message: Message) -> str:
    parts: list[str] = []
    for part in message.parts:
        text = part.text.strip() if part.text else ""
        if text:
            parts.append(text)
    return "\n".join(parts)


def _stream_response_text(response: StreamResponse) -> str:
    chunks: list[str] = []

    if response.HasField("message"):
        text = _message_text(response.message)
        if text:
            chunks.append(text)

    if response.HasField("task"):
        task = response.task
        if task.status.HasField("message"):
            text = _message_text(task.status.message)
            if text:
                chunks.append(text)
        for msg in task.history:
            if msg.role == Role.ROLE_AGENT:
                text = _message_text(msg)
                if text:
                    chunks.append(text)

    if response.HasField("status_update") and response.status_update.HasField("status"):
        text = _message_text(response.status_update.status.message)
        if text:
            chunks.append(text)

    return "\n".join(chunks)


def _build_send_request(message: str) -> SendMessageRequest:
    request = SendMessageRequest()
    request.message.role = Role.ROLE_USER
    request.message.parts.add().text = message.strip()
    return request


async def _call_a2a_subagent(agent_url: str, message: str) -> str:
    timeout = httpx.Timeout(_A2A_TIMEOUT_SECONDS, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http:
        factory = ClientFactory(
            ClientConfig(
                httpx_client=http,
                streaming=True,
                polling=False,
            ),
        )
        client = await factory.create_from_url(agent_url)
        try:
            collected: list[str] = []
            async for event in client.send_message(_build_send_request(message)):
                text = _stream_response_text(event)
                if text and (not collected or text != collected[-1]):
                    collected.append(text)
        finally:
            await client.close()

    if not collected:
        return "Subagent returned no text."

    result = collected[-1].strip()
    if len(result) > _RESPONSE_MAX_CHARS:
        return result[: _RESPONSE_MAX_CHARS - 3] + "..."
    return result


@tool
async def list_registered_subagents(runtime: ToolRuntime) -> str:
    """List A2A subagents the user registered and enabled on the SubAgent page."""
    if not settings.SUBAGENTS_ENABLED:
        return "Subagents are disabled."

    try:
        user_id = UUID(get_user_id_from_run(runtime))
        rows = await _enabled_subagents(user_id)
        if not rows:
            return (
                "No enabled subagents. The user can register remote A2A agents "
                "on the SubAgent page."
            )

        lines: list[str] = []
        for row in rows:
            card = row.agent_card if isinstance(row.agent_card, dict) else {}
            lines.append(
                f"- id={row.id} name={row.name!r}: {row.description or '(no description)'}\n"
                f"  url={row.agent_url}\n"
                f"  skills: {_format_skills(card)}",
            )
        return "Registered subagents:\n" + "\n".join(lines)
    except Exception as exc:
        logger.exception("list_registered_subagents_failed")
        return f"Could not list subagents: {exc}"


@tool
async def call_subagent(subagent_id: str, message: str, runtime: ToolRuntime) -> str:
    """Send a task message to a registered A2A subagent and return its reply.

    subagent_id: UUID or exact/partial subagent name from list_registered_subagents.
    message: The task or question to send to the remote agent.
    """
    if not settings.SUBAGENTS_ENABLED:
        return "Subagents are disabled."

    task = message.strip()
    if not task:
        return "message cannot be empty."

    try:
        user_id = UUID(get_user_id_from_run(runtime))
        row = await _resolve_subagent(user_id, subagent_id.strip())
        if row is None:
            return (
                f"No enabled subagent matched {subagent_id!r}. "
                "Call list_registered_subagents first."
            )

        reply = await _call_a2a_subagent(row.agent_url, task)

        factory = get_async_session_factory()
        async with factory() as session:
            db_row = await session.get(UserSubagent, row.id)
            if db_row is not None:
                from app.utils.datetime import now_utc

                db_row.last_error = None
                db_row.updated_at = now_utc()
                session.add(db_row)
                await session.commit()

        return f"[{row.name}] {reply}"
    except Exception as exc:
        logger.exception(
            "call_subagent_failed subagent_id=%s",
            subagent_id,
        )
        return f"Subagent call failed: {exc}"
