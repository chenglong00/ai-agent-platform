"""Minimal deep agent with a check_weather tool."""

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import MemorySaver

from app.ai.chat_agent.tools import check_weather
from app.ai.config import AgentSettings

_agent: Runnable | None = None
_checkpointer = MemorySaver()

_SYSTEM_PROMPT = """You are a helpful assistant.
When the user asks about weather, call check_weather with their location.
Summarize the result briefly."""


def get_deep_agent() -> Runnable:
    global _agent
    if _agent is not None:
        return _agent

    cfg = AgentSettings.deep_agent["agent_config"]
    model = init_chat_model(
        model=cfg["model"],
        model_provider=cfg["model_provider"],
        project=cfg["vertex_project"],
        location=cfg["vertex_location"],
        temperature=float(cfg["temperature"]),
        max_output_tokens=int(cfg["max_output_tokens"]),
        streaming=True,
        disable_streaming=False,
    )
    _agent = create_deep_agent(
        model=model,
        tools=[check_weather],
        system_prompt=_SYSTEM_PROMPT,
        checkpointer=_checkpointer,
    )
    return _agent


def reset_deep_agent() -> None:
    global _agent
    _agent = None
