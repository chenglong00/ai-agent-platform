from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from app.ai.config import AgentSettings
from app.ai.utils.markdown import read_markdown_file
from app.ai.tools.internet_search import internet_search

def get_research_subagent_spec() -> dict:
    base_prompt = read_markdown_file("app/ai/prompts/research.md")
    system_prompt = (
        base_prompt
        + "\n\nReturn a complete final answer in this run. "
        + "Do not say you are waiting or still processing."
    )
    cfg = AgentSettings.deep_agent["agent_config"]
    model = init_chat_model(
        model=cfg["model"],
        model_provider=cfg["model_provider"],
        project=cfg["vertex_project"],
        location=cfg["vertex_location"],
        temperature=float(cfg["temperature"]),
        max_output_tokens=int(cfg["max_output_tokens"]),
    )
    runnable = create_agent(
        model=model,
        system_prompt=system_prompt,
        tools=[internet_search],
    )
    return {
        "name": "research-agent",
        "description": "Used to research more in depth questions",
        "runnable": runnable,
    }