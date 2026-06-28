"""Prompt loading, orchestrator tools, and subagent specs."""

from pathlib import Path

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from app.ai.config import AgentSettings
from app.ai.skills import SKILLS_DIR
from app.ai.tools.todos import set_todos

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

ORCHESTRATOR_TOOLS = [set_todos]


def read_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def build_chat_model(*, streaming: bool = False):
    cfg = AgentSettings.deep_agent["agent_config"]
    return init_chat_model(
        model=cfg["model"],
        model_provider=cfg["model_provider"],
        project=cfg["vertex_project"],
        location=cfg["vertex_location"],
        temperature=float(cfg["temperature"]),
        max_output_tokens=int(cfg["max_output_tokens"]),
        streaming=streaming,
        disable_streaming=not streaming,
    )