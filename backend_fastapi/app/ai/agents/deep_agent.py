from deepagents import create_deep_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import MemorySaver

from app.ai.agents.subagents.funding import get_funding_subagent_spec
from app.ai.agents.subagents.report import get_report_subagent_spec
from app.ai.agents.subagents.research import get_research_subagent_spec
from app.ai.backend.factory import build_backend
from app.ai.config import AgentSettings
from app.ai.middleware.log import log_tool_calls
from app.ai.utils.skills_paths import ensure_skills
from app.ai.tools.todos import set_todos
from app.ai.utils.markdown import read_markdown_file

# Singleton — state must survive across the interrupt → resume round-trip.
_agent: Runnable | None = None
_checkpointer = MemorySaver()


def get_deep_agent() -> Runnable:
    global _agent
    if _agent is not None:
        return _agent

    system_prompt = read_markdown_file("app/ai/prompts/deep_agent.md")
    config = AgentSettings.deep_agent["agent_config"]
    model = init_chat_model(
        model=config["model"],
        model_provider=config["model_provider"],
        project=config["vertex_project"],
        location=config["vertex_location"],
        temperature=float(config["temperature"]),
        max_output_tokens=int(config["max_output_tokens"]),
        streaming=True,
        disable_streaming=False,
    )
    backend = build_backend()
    _agent = create_deep_agent(
        model=model,
        tools=[set_todos],
        subagents=[
            get_research_subagent_spec(),
            get_funding_subagent_spec(),
            get_report_subagent_spec(),
        ],
        skills=str(ensure_skills()),
        backend=backend,
        middleware=[
            log_tool_calls,
            HumanInTheLoopMiddleware(interrupt_on={"internet_search": True}),
        ],
        system_prompt=system_prompt,
        checkpointer=_checkpointer,
    )
    return _agent


def reset_deep_agent() -> None:
    """Drop the cached agent so the next call rebuilds it (e.g. after sandbox reset)."""
    global _agent
    _agent = None
