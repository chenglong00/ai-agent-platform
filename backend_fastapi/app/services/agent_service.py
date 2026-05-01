"""Agent runners — text replies via LangGraph agents (routing by ``AgentType`` TBD)."""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from app.ai.config import AgentSettings
from app.ai.agents.deep_agent import get_deep_agent
from app.models.agent import AgentType
from app.schemas.chat import PendingToolCall

logger = logging.getLogger(__name__)

_APPROVE_PHRASES = {"yes", "y", "ok", "okay", "approve", "go ahead", "sure", "proceed"}
_REJECT_PHRASES = {"no", "n", "cancel", "stop", "reject", "don't", "dont"}


class AgentService:
    """Invokes configured agents and normalizes graph output to plain assistant text."""

    @staticmethod
    def _text_from_content(c: Any) -> str:
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts: list[str] = []
            for item in c:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts) if parts else str(c)
        return str(c)

    @staticmethod
    def _text_from_ai_message(msg: AIMessage) -> str:
        return AgentService._text_from_content(msg.content)

    @staticmethod
    def _message_role(msg: Any) -> str:
        """Best-effort message role extraction across LC message variants."""
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
        """Best-effort content extraction across dict/object messages."""
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
    def _build_run_config(thread_id: str) -> dict:
        return {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": AgentService._recursion_limit(),
        }

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
        """Return pending tool calls if the graph is currently interrupted, else []."""
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
                # HumanInTheLoopMiddleware passes a list of ActionRequest dicts
                items = value if isinstance(value, list) else [value] if value else []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    pending.append(PendingToolCall(
                        tool_name=item.get("name", "unknown"),
                        args=item.get("args", {}),
                        description=item.get("description", ""),
                    ))
        return pending

    @staticmethod
    def _assistant_text_from_agent_result(result: Any) -> str:
        """``create_agent`` graphs return state dicts with a ``messages`` list."""
        if isinstance(result, AIMessage):
            return AgentService._text_from_ai_message(result)
        if isinstance(result, dict):
            messages = result.get("messages")
            if isinstance(messages, list):
                return AgentService._assistant_text_from_messages(messages)
        return ""

    @staticmethod
    def _assistant_text_from_messages(messages: list[Any]) -> str:
        # Prefer the latest non-empty assistant message.
        for msg in reversed(messages):
            role = AgentService._message_role(msg)
            if isinstance(msg, AIMessage) or role in {"assistant", "ai"}:
                text = AgentService._text_from_content(
                    AgentService._message_content(msg)
                ).strip()
                if text:
                    return text
        # Fallback: if no assistant text was emitted after a tool call, use
        # the latest tool output so the API still returns a useful reply.
        for msg in reversed(messages):
            role = AgentService._message_role(msg)
            if isinstance(msg, ToolMessage) or role in {"tool", "toolmessage"}:
                text = AgentService._text_from_content(
                    AgentService._message_content(msg)
                ).strip()
                if text:
                    return text
        return ""

    async def reply(
        self,
        agent_type: AgentType | None,
        user_text: str,
        *,
        conversation_id: UUID | None = None,
        conversation_history: list[tuple[str, str]] | None = None,
    ) -> tuple[str, list[PendingToolCall]]:
        """Return (assistant_text, pending_tool_calls).

        pending_tool_calls is non-empty when the agent paused for human approval.
        """
        t0 = time.monotonic()
        agent = get_deep_agent()
        thread_id = str(conversation_id) if conversation_id else "default"
        config: dict = self._build_run_config(thread_id)

        # Check whether the graph is already paused from a previous turn.
        pending_before = self._pending_tool_calls(agent, config)
        is_resuming = bool(pending_before)

        if is_resuming:
            normalized = user_text.strip().lower()
            if normalized in _APPROVE_PHRASES:
                decision = [{"type": "approve"}]
                logger.debug("agent_interrupt_approve thread_id=%s", thread_id)
            else:
                decision = [{"type": "reject", "message": user_text}]
                logger.debug("agent_interrupt_reject thread_id=%s", thread_id)
            invoke_input: Any = Command(resume=decision)
        else:
            input_messages = self._build_messages(user_text, conversation_history)
            invoke_input = {"messages": input_messages}

        logger.debug(
            "agent_reply_start agent_type=%s user_chars=%s resuming=%s thread_id=%s",
            agent_type, len(user_text), is_resuming, thread_id,
        )

        timeout_s = self._agent_timeout_seconds()
        recursed = False
        try:
            out = await asyncio.wait_for(
                agent.ainvoke(invoke_input, config=config),
                timeout=timeout_s,
            )
        except TimeoutError:
            logger.warning(
                "agent_reply_timeout agent_type=%s timeout_s=%.1f", agent_type, timeout_s
            )
            raise
        except GraphRecursionError:
            logger.warning(
                "agent_reply_recursion_limit agent_type=%s thread_id=%s limit=%s",
                agent_type, thread_id, self._recursion_limit(),
            )
            recursed = True
            out = None

        # Check if the graph paused again after this turn (new interrupt).
        pending_after = self._pending_tool_calls(agent, config)

        if pending_after:
            calls_summary = ", ".join(
                f"`{p.tool_name}({p.args})`" for p in pending_after
            )
            text = (
                f"⏸ I want to call {calls_summary}.\n\n"
                "Reply **yes** to approve or **no** to cancel."
            )
        else:
            text = self._assistant_text_from_agent_result(out) if out is not None else ""
            if not text.strip():
                explained = self._explain_empty_ai_message(agent, config)
                if recursed and not explained:
                    explained = (
                        "The agent stopped after reaching the maximum step limit "
                        f"({self._recursion_limit()}). Please simplify your request or try again."
                    )
                text = explained or (
                    "I completed the request but couldn't produce a visible reply. Please try again."
                )

        logger.debug(
            "agent_reply_done agent_type=%s assistant_chars=%s interrupted=%s duration_ms=%.1f",
            agent_type, len(text), bool(pending_after), (time.monotonic() - t0) * 1000,
        )
        return text, pending_after

    _FINISH_REASON_MESSAGES: dict[str, str] = {
        "MALFORMED_FUNCTION_CALL": (
            "The model produced a malformed tool call and stopped before generating a reply. "
            "Please rephrase your request or try again."
        ),
        "SAFETY": (
            "The model's response was blocked by safety filters. "
            "Please rephrase your request."
        ),
        "RECITATION": (
            "The model stopped the response due to a recitation policy. "
            "Please rephrase your request."
        ),
        "MAX_TOKENS": (
            "The model hit the output token limit before producing a reply. "
            "Try a shorter or more focused request."
        ),
        "PROHIBITED_CONTENT": (
            "The model declined to respond due to prohibited content. "
            "Please rephrase your request."
        ),
    }

    @staticmethod
    def _explain_empty_ai_message(agent: Any, config: dict) -> str:
        """If last AI message is empty, return a user-friendly reason if known."""
        try:
            state = agent.get_state(config)
        except Exception:
            return ""
        values = getattr(state, "values", None)
        if not isinstance(values, dict):
            return ""
        msgs = values.get("messages")
        if not isinstance(msgs, list):
            return ""
        last_ai = next(
            (
                m for m in reversed(msgs)
                if isinstance(m, AIMessage)
                or AgentService._message_role(m) in {"assistant", "ai"}
            ),
            None,
        )
        if last_ai is None:
            return ""
        response_metadata = getattr(last_ai, "response_metadata", None)
        if not isinstance(response_metadata, dict):
            return ""
        finish_reason = str(response_metadata.get("finish_reason") or "")
        return AgentService._FINISH_REASON_MESSAGES.get(finish_reason, "")

    @staticmethod
    def _assistant_text_from_graph_state(
        agent: Any,
        config: dict,
        *,
        min_message_index: int = 0,
    ) -> str:
        """Read latest assistant text from graph state for non-streamed completions."""
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

        scoped_messages = msgs[min_message_index:] if min_message_index > 0 else msgs
        return AgentService._assistant_text_from_messages(scoped_messages).strip()


    async def stream_reply(
        self,
        agent_type: AgentType | None,
        user_text: str,
        *,
        conversation_id: UUID | None = None,
        conversation_history: list[tuple[str, str]] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Yield SSE-ready event dicts while the agent runs.

        Event types emitted:
          subagent_start  {id, subagent_type, description, started_at}
          subagent_token  {id, content}
          subagent_done   {id, result, status, completed_at}
          token           {content}   — main-agent token
          interrupt       {pending_tool_calls}
          done            {full_text, interrupted}
        """
        import time as _time

        agent = get_deep_agent()
        thread_id = str(conversation_id) if conversation_id else "default"
        config: dict = self._build_run_config(thread_id)
        logger.debug(
            "stream_reply_start agent_type=%s thread_id=%s user_chars=%s history_turns=%s",
            agent_type,
            thread_id,
            len(user_text),
            len(conversation_history or []),
        )

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
            invoke_input = {"messages": self._build_messages(user_text, conversation_history)}

        full_text_parts: list[str] = []
        main_token_chunks = 0
        subagent_token_chunks = 0
        dropped_planning_chunks = 0
        event_count = 0
        event_type_counts: dict[str, int] = {}

        # tool_call_id → subagent info (populated on on_tool_start for "task")
        subagent_by_call: dict[str, dict] = {}
        # namespace → tool_call_id (populated when subgraph events arrive)
        ns_to_call_id: dict[str, str] = {}
        # Track task lifecycle to distinguish planning tokens from synthesis tokens.
        # Planning = main-model call BEFORE any task tool; those tokens must be
        # suppressed so subagent cards appear before any text.
        # Synthesis = main-model call AFTER all tasks finish; those tokens are shown.
        task_started = 0
        task_ended = 0

        recursed = False
        _events_iter = agent.astream_events(
            invoke_input, config=config, version="v2", subgraphs=True
        ).__aiter__()
        while True:
            try:
                event = await _events_iter.__anext__()
            except StopAsyncIteration:
                break
            except GraphRecursionError:
                logger.warning(
                    "stream_reply_recursion_limit thread_id=%s limit=%s events_so_far=%s",
                    thread_id, self._recursion_limit(), event_count,
                )
                recursed = True
                break
            event_count += 1
            etype = event["event"]
            event_type_counts[etype] = event_type_counts.get(etype, 0) + 1
            ns: str = event.get("metadata", {}).get("langgraph_checkpoint_ns", "")
            # Namespace structure from deepagents/LangGraph:
            #   ""                        → top-level chain (rare)
            #   "model:<uuid>"            → main agent model node
            #   "tools:<uuid>"            → task tool node (where subagents launch)
            #   "tools:<uuid>|model:<u>"  → model node inside a subagent
            is_subagent_ns = "|" in ns
            is_task_tool_ns = ns.startswith("tools:") and not is_subagent_ns
            is_main_model_ns = not is_subagent_ns and not is_task_tool_ns

            # ── task tool start → register a new subagent / handle set_todos ──
            if etype == "on_tool_start" and is_task_tool_ns:
                tool_name = event.get("name", "")
                if tool_name == "set_todos":
                    # Emit todos immediately so the UI updates before work begins.
                    raw_todos = (event["data"].get("input") or {}).get("todos", [])
                    serialized = []
                    for t in raw_todos:
                        if hasattr(t, "model_dump"):
                            serialized.append(t.model_dump())
                        elif isinstance(t, dict):
                            serialized.append(t)
                    yield {"type": "todos_update", "todos": serialized}
                elif tool_name == "task":
                    task_started += 1
                    call_id = event.get("run_id", event.get("id", tool_name))
                    args = event["data"].get("input") or {}
                    subagent_type = str(args.get("subagent_type") or args.get("agent") or "agent")
                    description = str(args.get("description") or "")
                    started_at = int(_time.time() * 1000)
                    subagent_by_call[call_id] = {
                        "id": call_id,
                        "subagent_type": subagent_type,
                        "description": description,
                        "started_at": started_at,
                        "status": "running",
                    }
                    yield {
                        "type": "subagent_start",
                        "id": call_id,
                        "subagent_type": subagent_type,
                        "description": description,
                        "started_at": started_at,
                    }

            # ── subgraph model stream → subagent tokens ───────────────────────
            elif etype == "on_chat_model_stream" and is_subagent_ns:
                raw = event["data"].get("chunk")
                content = raw.content if hasattr(raw, "content") else (raw or "")
                if isinstance(content, list):
                    content = "".join(
                        c.get("text", "") if isinstance(c, dict) else str(c)
                        for c in content
                    )
                if not isinstance(content, str) or not content:
                    continue
                subagent_token_chunks += 1

                # Map namespace to a call_id on first token.
                # The subagent ns looks like "tools:<task_run_id>|model:<uuid>".
                # Extract the task run_id from the prefix to match subagent_by_call.
                if ns not in ns_to_call_id:
                    parent_ns = ns.split("|")[0]  # "tools:<task_run_id>"
                    matched = next(
                        (cid for cid in subagent_by_call if parent_ns.endswith(cid) or cid in parent_ns),
                        None,
                    )
                    if matched is None:
                        # Fallback: most recent running subagent not yet mapped
                        pending = [
                            cid for cid, info in subagent_by_call.items()
                            if info["status"] == "running" and cid not in ns_to_call_id.values()
                        ]
                        matched = pending[-1] if pending else ns
                    ns_to_call_id[ns] = matched

                yield {"type": "subagent_token", "id": ns_to_call_id[ns], "content": content}

            # ── main model stream → main agent tokens ─────────────────────────
            # Only emit when we're in synthesis (all tasks done) or it's a direct
            # response with no task tools at all. This prevents planning-phase tokens
            # (model thinking about which subagents to call) from appearing as text
            # before the subagent cards render.
            elif etype == "on_chat_model_stream" and is_main_model_ns:
                in_synthesis = task_started == 0 or task_ended >= task_started
                if not in_synthesis:
                    dropped_planning_chunks += 1
                    continue
                raw = event["data"].get("chunk")
                content = raw.content if hasattr(raw, "content") else (raw or "")
                if isinstance(content, list):
                    content = "".join(
                        c.get("text", "") if isinstance(c, dict) else str(c)
                        for c in content
                    )
                if isinstance(content, str) and content:
                    full_text_parts.append(content)
                    main_token_chunks += 1
                    yield {"type": "token", "content": content}

            # ── task tool end → subagent complete ─────────────────────────────
            elif etype == "on_tool_end" and is_task_tool_ns:
                tool_name = event.get("name", "")
                if tool_name == "task":
                    task_ended += 1
                    call_id = event.get("run_id", event.get("id", ""))
                    info = subagent_by_call.get(call_id, {})
                    if info:
                        result_raw = event["data"].get("output", "")
                        result = str(result_raw) if result_raw else ""
                        completed_at = int(_time.time() * 1000)
                        subagent_by_call[call_id]["status"] = "complete"
                        yield {
                            "type": "subagent_done",
                            "id": call_id,
                            "result": result,
                            "status": "complete",
                            "completed_at": completed_at,
                        }

        pending_after = self._pending_tool_calls(agent, config)
        if pending_after:
            yield {
                "type": "interrupt",
                "pending_tool_calls": [
                    {"tool_name": p.tool_name, "args": p.args, "description": p.description}
                    for p in pending_after
                ],
            }

        full_text = "".join(full_text_parts).strip()
        used_state_fallback = False
        if not full_text and not pending_after:
            # Some models batch the final answer into graph state without
            # emitting incremental token events for the main model stream.
            full_text = self._assistant_text_from_graph_state(
                agent,
                config,
                min_message_index=initial_message_count,
            )
            used_state_fallback = bool(full_text)

        explained = ""
        if not full_text and not pending_after:
            explained = self._explain_empty_ai_message(agent, config)
            if recursed and not explained:
                explained = (
                    "The agent stopped after reaching the maximum step limit "
                    f"({self._recursion_limit()}). Please simplify your request or try again."
                )
            full_text = explained or (
                "I completed the request but couldn't produce a visible reply. Please try again."
            )

        # Fake-stream fallback: when the model didn't emit incremental tokens
        # (common with Gemini Vertex when tools are bound), chunk the final
        # text so the UI animates it in instead of dumping it at the end.
        fake_streamed = (
            bool(full_text) and main_token_chunks == 0 and not pending_after
        )
        if fake_streamed:
            chunk_size = 32
            for i in range(0, len(full_text), chunk_size):
                yield {"type": "token", "content": full_text[i : i + chunk_size]}
                await asyncio.sleep(0.02)

        logger.debug(
            "stream_reply_done thread_id=%s events=%s main_chunks=%s sub_chunks=%s "
            "dropped=%s text_chars=%s interrupted=%s recursed=%s "
            "state_fallback=%s explained=%s fake_streamed=%s event_types=%s",
            thread_id,
            event_count,
            main_token_chunks,
            subagent_token_chunks,
            dropped_planning_chunks,
            len(full_text),
            bool(pending_after),
            recursed,
            used_state_fallback,
            bool(explained),
            fake_streamed,
            event_type_counts,
        )

        yield {"type": "done", "full_text": full_text, "interrupted": bool(pending_after)}


agent_service = AgentService()
