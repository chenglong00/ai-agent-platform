"""Agent runners — invoke the LangGraph deep agent and stream SSE events."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from app.ai.chat_agent.graph import get_deep_agent
from app.ai.config import AgentSettings
from app.modules.agent.model import AgentType
from app.modules.chat.stream_blocks import TurnBlockCollector
from app.modules.chat.schema import PendingToolCall

logger = logging.getLogger(__name__)

_APPROVE_PHRASES = {"yes", "y", "ok", "okay", "approve", "go ahead", "sure", "proceed"}


class AgentService:
    """Invokes the deep agent and normalizes graph output to assistant text."""

    @staticmethod
    def _text_from_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts) if parts else str(content)
        return str(content)

    @staticmethod
    def _message_role(msg: Any) -> str:
        if isinstance(msg, dict):
            return str(msg.get("role") or msg.get("type") or "").lower()
        role = getattr(msg, "role", None)
        if role:
            return str(role).lower()
        mtype = getattr(msg, "type", None)
        if mtype:
            return str(mtype).lower()
        return ""

    @staticmethod
    def _message_content(msg: Any) -> Any:
        if isinstance(msg, dict):
            return msg.get("content", "")
        return getattr(msg, "content", "")

    @staticmethod
    def _agent_timeout_seconds() -> float:
        cfg = AgentSettings.deep_agent.get("agent_config", {})
        raw = cfg.get("timeout_seconds", 90)
        try:
            timeout = float(raw)
        except (TypeError, ValueError):
            timeout = 90.0
        return max(timeout, 1.0)

    @staticmethod
    def _recursion_limit() -> int:
        cfg = AgentSettings.deep_agent.get("agent_config", {})
        raw = cfg.get("recursion_limit", 25)
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            limit = 25
        return max(limit, 1)

    @staticmethod
    def _history_turn_limit() -> int:
        cfg = AgentSettings.deep_agent.get("agent_config", {})
        raw = cfg.get("history_turn_limit", 20)
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            limit = 20
        return max(limit, 0)

    @staticmethod
    def _build_run_config(thread_id: str) -> dict:
        return {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": AgentService._recursion_limit(),
        }

    @staticmethod
    def _build_messages(
        user_text: str,
        conversation_history: list[tuple[str, str]] | None,
    ) -> list[HumanMessage | AIMessage]:
        messages: list[HumanMessage | AIMessage] = []
        history_limit = AgentService._history_turn_limit()
        turns = (conversation_history or [])[-history_limit:] if history_limit else []
        for role, content in turns:
            text = content.strip()
            if not text:
                continue
            if role == "assistant":
                messages.append(AIMessage(content=text))
            else:
                messages.append(HumanMessage(content=text))
        messages.append(HumanMessage(content=user_text))
        return messages

    @staticmethod
    def _pending_tool_calls(agent: Any, config: dict) -> list[PendingToolCall]:
        try:
            state = agent.get_state(config)
        except Exception:
            return []
        if not getattr(state, "next", None):
            return []
        pending: list[PendingToolCall] = []
        for task in getattr(state, "tasks", []):
            for interrupt in getattr(task, "interrupts", []):
                value = getattr(interrupt, "value", None)
                items = value if isinstance(value, list) else [value] if value else []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    pending.append(
                        PendingToolCall(
                            tool_name=item.get("name", "unknown"),
                            args=item.get("args", {}),
                            description=item.get("description", ""),
                        ),
                    )
        return pending

    @staticmethod
    def _assistant_text_from_messages(messages: list[Any]) -> str:
        for msg in reversed(messages):
            role = AgentService._message_role(msg)
            if isinstance(msg, AIMessage) or role in {"assistant", "ai"}:
                text = AgentService._text_from_content(
                    AgentService._message_content(msg),
                ).strip()
                if text:
                    return text
        for msg in reversed(messages):
            role = AgentService._message_role(msg)
            if isinstance(msg, ToolMessage) or role in {"tool", "toolmessage"}:
                text = AgentService._text_from_content(
                    AgentService._message_content(msg),
                ).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _assistant_text_from_agent_result(result: Any) -> str:
        if isinstance(result, AIMessage):
            return AgentService._text_from_content(result.content)
        if isinstance(result, dict):
            messages = result.get("messages")
            if isinstance(messages, list):
                return AgentService._assistant_text_from_messages(messages)
        return ""

    @staticmethod
    def _assistant_text_from_graph_state(
        agent: Any,
        config: dict,
        *,
        min_message_index: int = 0,
    ) -> str:
        try:
            state = agent.get_state(config)
        except Exception:
            logger.exception("agent_state_read_failed")
            return ""
        values = getattr(state, "values", None)
        if not isinstance(values, dict):
            return ""
        msgs = values.get("messages")
        if not isinstance(msgs, list):
            return ""
        scoped = msgs[min_message_index:] if min_message_index > 0 else msgs
        return AgentService._assistant_text_from_messages(scoped).strip()

    async def reply(
        self,
        agent_type: AgentType | None,
        user_text: str,
        *,
        conversation_id: UUID | None = None,
        conversation_history: list[tuple[str, str]] | None = None,
    ) -> tuple[str, list[PendingToolCall]]:
        agent = get_deep_agent()
        thread_id = str(conversation_id) if conversation_id else "default"
        config = self._build_run_config(thread_id)

        pending_before = self._pending_tool_calls(agent, config)
        if pending_before:
            normalized = user_text.strip().lower()
            decision = (
                [{"type": "approve"}]
                if normalized in _APPROVE_PHRASES
                else [{"type": "reject", "message": user_text}]
            )
            invoke_input: Any = Command(resume=decision)
        else:
            invoke_input = {
                "messages": self._build_messages(user_text, conversation_history),
            }

        timeout_s = self._agent_timeout_seconds()
        recursed = False
        try:
            out = await asyncio.wait_for(
                agent.ainvoke(invoke_input, config=config),
                timeout=timeout_s,
            )
        except TimeoutError:
            logger.warning("agent_reply_timeout agent_type=%s timeout_s=%.1f", agent_type, timeout_s)
            raise
        except GraphRecursionError:
            logger.warning(
                "agent_reply_recursion_limit agent_type=%s thread_id=%s",
                agent_type,
                thread_id,
            )
            recursed = True
            out = None

        pending_after = self._pending_tool_calls(agent, config)
        if pending_after:
            calls_summary = ", ".join(f"`{p.tool_name}({p.args})`" for p in pending_after)
            text = (
                f"I want to call {calls_summary}.\n\n"
                "Reply **yes** to approve or **no** to cancel."
            )
        else:
            text = self._assistant_text_from_agent_result(out) if out is not None else ""
            if not text.strip():
                if recursed:
                    text = (
                        "The agent stopped after reaching the maximum step limit "
                        f"({self._recursion_limit()}). Please simplify your request or try again."
                    )
                else:
                    text = (
                        "I completed the request but couldn't produce a visible reply. "
                        "Please try again."
                    )

        return text, pending_after

    @staticmethod
    def _tool_output_text(output: Any) -> str:
        if output is None:
            return ""
        if isinstance(output, ToolMessage):
            return AgentService._text_from_content(output.content)
        if hasattr(output, "content"):
            return AgentService._text_from_content(getattr(output, "content"))
        if isinstance(output, dict) and "content" in output:
            return AgentService._text_from_content(output["content"])
        return str(output)

    @staticmethod
    def _tool_input_dict(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if raw is None:
            return {}
        return {"input": raw}

    async def stream_reply(
        self,
        agent_type: AgentType | None,
        user_text: str,
        *,
        conversation_id: UUID | None = None,
        conversation_history: list[tuple[str, str]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Yield SSE-ready event dicts while the agent runs."""
        agent = get_deep_agent()
        thread_id = str(conversation_id) if conversation_id else "default"
        config = self._build_run_config(thread_id)

        pending_before = self._pending_tool_calls(agent, config)
        initial_message_count = 0
        try:
            state_before = agent.get_state(config)
            values_before = getattr(state_before, "values", None)
            if isinstance(values_before, dict) and isinstance(values_before.get("messages"), list):
                initial_message_count = len(values_before["messages"])
        except Exception:
            pass

        if pending_before:
            normalized = user_text.strip().lower()
            decision = (
                [{"type": "approve"}]
                if normalized in _APPROVE_PHRASES
                else [{"type": "reject", "message": user_text}]
            )
            invoke_input: Any = Command(resume=decision)
        else:
            invoke_input = {
                "messages": self._build_messages(user_text, conversation_history),
            }

        full_text_parts: list[str] = []
        token_chunks = 0
        recursed = False
        turn_blocks = TurnBlockCollector()

        stream = await agent.astream_events(
            invoke_input,
            config=config,
            version="v3",
        )
        outbound: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async with stream:

            async def emit_tool_calls() -> None:
                async for tool_call in stream.tool_calls:
                    if tool_call.tool_name == "task":
                        async for _ in tool_call.output_deltas:
                            pass
                        continue

                    args = (
                        tool_call.input
                        if isinstance(tool_call.input, dict)
                        else self._tool_input_dict(tool_call.input)
                    )
                    call_id = tool_call.tool_call_id
                    started_at = int(time.time() * 1000)

                    await outbound.put({
                        "type": "tool_call_start",
                        "id": call_id,
                        "tool_name": tool_call.tool_name,
                        "args": args,
                        "started_at": started_at,
                    })

                    async for _ in tool_call.output_deltas:
                        pass

                    completed_at = int(time.time() * 1000)
                    if tool_call.error:
                        await outbound.put({
                            "type": "tool_call_end",
                            "id": call_id,
                            "tool_name": tool_call.tool_name,
                            "result": tool_call.error,
                            "status": "error",
                            "completed_at": completed_at,
                        })
                    else:
                        await outbound.put({
                            "type": "tool_call_end",
                            "id": call_id,
                            "tool_name": tool_call.tool_name,
                            "result": self._tool_output_text(tool_call.output),
                            "status": "complete",
                            "completed_at": completed_at,
                        })

            async def emit_messages() -> None:
                async for message in stream.messages:
                    async for token in message.text:
                        if token:
                            await outbound.put({"type": "token", "content": token})

            async def emit_subagents() -> None:
                async for subagent in stream.subagents:
                    sa_id = subagent.trigger_call_id or str(uuid4())
                    started_at = int(time.time() * 1000)
                    await outbound.put({
                        "type": "subagent_start",
                        "id": sa_id,
                        "subagent_type": subagent.name or "agent",
                        "description": "",
                        "started_at": started_at,
                    })

                    content_parts: list[str] = []
                    async for message in subagent.messages:
                        async for token in message.text:
                            if not token:
                                continue
                            content_parts.append(token)
                            await outbound.put({
                                "type": "subagent_token",
                                "id": sa_id,
                                "content": token,
                            })

                    result = "".join(content_parts)
                    status = "complete"
                    try:
                        output = await subagent.output
                        if not result.strip() and output is not None:
                            result = self._tool_output_text(output)
                    except Exception:
                        status = "error"
                        if not result:
                            result = "Subagent failed"

                    await outbound.put({
                        "type": "subagent_done",
                        "id": sa_id,
                        "result": result,
                        "status": status,
                        "completed_at": int(time.time() * 1000),
                    })

            async def run_projections() -> bool:
                hit_recursion_limit = False
                try:
                    results = await asyncio.gather(
                        emit_tool_calls(),
                        emit_messages(),
                        emit_subagents(),
                        return_exceptions=True,
                    )
                    for result in results:
                        if isinstance(result, GraphRecursionError):
                            hit_recursion_limit = True
                            logger.warning("stream_reply_recursion_limit thread_id=%s", thread_id)
                        elif isinstance(result, Exception):
                            raise result
                finally:
                    await outbound.put(None)
                return hit_recursion_limit

            projections = asyncio.create_task(run_projections())
            try:
                while True:
                    event = await outbound.get()
                    if event is None:
                        break
                    if event.get("type") == "token":
                        content = event.get("content", "")
                        if content:
                            full_text_parts.append(content)
                            token_chunks += 1
                    turn_blocks.observe(event)
                    yield event
            finally:
                recursed = await projections

        pending_after = self._pending_tool_calls(agent, config)
        if pending_after:
            yield {
                "type": "interrupt",
                "pending_tool_calls": [
                    {
                        "tool_name": p.tool_name,
                        "args": p.args,
                        "description": p.description,
                    }
                    for p in pending_after
                ],
            }

        full_text = "".join(full_text_parts).strip()
        if not full_text and not pending_after:
            full_text = self._assistant_text_from_graph_state(
                agent,
                config,
                min_message_index=initial_message_count,
            )

        if not full_text and not pending_after:
            if recursed:
                full_text = (
                    "The agent stopped after reaching the maximum step limit "
                    f"({self._recursion_limit()}). Please simplify your request or try again."
                )
            else:
                full_text = (
                    "I completed the request but couldn't produce a visible reply. "
                    "Please try again."
                )

        if full_text and token_chunks == 0 and not pending_after:
            chunk_size = 32
            for i in range(0, len(full_text), chunk_size):
                yield {"type": "token", "content": full_text[i : i + chunk_size]}
                await asyncio.sleep(0.02)

        block_specs = [
            {"block_type": block_type.value, "payload": payload}
            for block_type, payload in turn_blocks.to_block_specs(full_text)
        ]

        yield {
            "type": "done",
            "full_text": full_text,
            "interrupted": bool(pending_after),
            "block_specs": block_specs,
        }


agent_service = AgentService()
