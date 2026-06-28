"""Deep agent with weather, sandbox, and optional Playwright browser tools."""

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import MemorySaver

from app.ai.chat_agent.backend_factory import (
    backend_for_runtime,
    shutdown_all_sandboxes,
)
from app.ai.chat_agent.knowledge_base_tools import search_knowledge_base
from app.ai.chat_agent.memory_tools import (
    list_user_memories,
    save_user_memory,
    search_user_memories,
)
from app.ai.chat_agent.playwright_pool import shutdown_all_browsers
from app.ai.chat_agent.playwright_tools import PLAYWRIGHT_BROWSER_TOOLS
from app.ai.chat_agent.tools import check_weather
from app.ai.config import AgentSettings
from app.ai.skills.tools import list_skills, read_skill
from app.core.config import settings

_agent: Runnable | None = None
_checkpointer = MemorySaver()

_SYSTEM_PROMPT_BASE = """You are a helpful assistant.
When the user asks about weather, call check_weather with their location.
For questions about uploaded documents, internal policies, or knowledge base content, call search_knowledge_base before answering.
For coding, files, or shell work use the built-in filesystem and execute tools in the sandbox."""

_SYSTEM_PROMPT_BROWSER = """
When the user asks to browse the web, research a site, fill a form, or interact with a page, use the browser_* tools one at a time (never call multiple browser tools in parallel):
1. browser_goto to open a URL
2. browser_read to inspect visible page text before acting
3. browser_click_text to click links/buttons by visible text; browser_click_role for role+name; browser_click only for real CSS selectors (#id, .class, a:has-text('…'))
4. browser_type, browser_press for form input and keys
5. browser_screenshot when the user should see the current page
The browser session stays open across these steps — do not try to close or reset it yourself.
Always browser_goto first, then browser_read, then other actions as needed.
Work step-by-step; read the page after navigation or clicks when unsure what to do next."""

_SYSTEM_PROMPT_SKILLS = """
Use list_skills to see skills available to this user, then read_skill with a skill id before following specialized workflows."""

_SYSTEM_PROMPT_MEMORY = """
Long-term memory about the user may appear in the message context. Use it to personalize replies.
When the user shares durable facts, preferences, or profile details, read the user-memory skill and call save_user_memory.
Use search_user_memories or list_user_memories when you need to recall what you know about the user."""

_SYSTEM_PROMPT_TAIL = "\nSummarize tool results briefly for the user."


def _system_prompt() -> str:
    parts = [_SYSTEM_PROMPT_BASE]
    if settings.BROWSER_PLAYWRIGHT_ENABLED:
        parts.append(_SYSTEM_PROMPT_BROWSER)
    if settings.DEEP_AGENT_SKILLS_ENABLED:
        parts.append(_SYSTEM_PROMPT_SKILLS)
    if settings.USER_MEMORY_ENABLED:
        parts.append(_SYSTEM_PROMPT_MEMORY)
    parts.append(_SYSTEM_PROMPT_TAIL)
    return "\n".join(parts)


def _agent_tools() -> list:
    tools = [check_weather]
    if settings.DEEP_AGENT_SKILLS_ENABLED:
        tools.extend([list_skills, read_skill])
    if settings.KNOWLEDGE_BASE_RAG_ENABLED:
        tools.append(search_knowledge_base)
    if settings.USER_MEMORY_ENABLED:
        tools.extend([save_user_memory, search_user_memories, list_user_memories])
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
