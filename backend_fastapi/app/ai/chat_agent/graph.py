"""Deep agent with weather, sandbox, and optional Playwright browser tools."""

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import MemorySaver

from app.ai.chat_agent.backend_factory import (
    backend_for_runtime,
    shutdown_all_sandboxes,
)
from app.ai.chat_agent.playwright_pool import shutdown_all_browsers
from app.ai.chat_agent.playwright_tools import PLAYWRIGHT_BROWSER_TOOLS
from app.ai.chat_agent.tools import check_weather
from app.ai.config import AgentSettings
from app.core.config import settings

_agent: Runnable | None = None
_checkpointer = MemorySaver()

_SYSTEM_PROMPT_BASE = """You are a helpful assistant.
When the user asks about weather, call check_weather with their location.
For coding, files, or shell work use the built-in filesystem and execute tools in the sandbox."""

_SYSTEM_PROMPT_BROWSER = """
When the user asks to browse the web, research a site, fill a form, or interact with a page, use the browser_* tools:
1. browser_goto to open a URL
2. browser_read to inspect visible page text before acting
3. browser_click, browser_type, browser_press for interactions
4. browser_screenshot when the user should see the current page
5. browser_close when finished
Work step-by-step; read the page after navigation or clicks when unsure what to do next."""

_SYSTEM_PROMPT_TAIL = "\nSummarize tool results briefly for the user."


def _system_prompt() -> str:
    parts = [_SYSTEM_PROMPT_BASE]
    if settings.BROWSER_PLAYWRIGHT_ENABLED:
        parts.append(_SYSTEM_PROMPT_BROWSER)
    parts.append(_SYSTEM_PROMPT_TAIL)
    return "\n".join(parts)


def _agent_tools() -> list:
    tools = [check_weather]
    if settings.BROWSER_PLAYWRIGHT_ENABLED:
        tools.extend(PLAYWRIGHT_BROWSER_TOOLS)
    return tools


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
        tools=_agent_tools(),
        system_prompt=_system_prompt(),
        backend=backend_for_runtime,
        checkpointer=_checkpointer,
    )
    return _agent


async def reset_deep_agent_async() -> None:
    global _agent
    shutdown_all_sandboxes()
    await shutdown_all_browsers()
    _agent = None


def reset_deep_agent() -> None:
    """Sync wrapper for tests and reload hooks."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(reset_deep_agent_async())
    else:
        loop.create_task(reset_deep_agent_async())
