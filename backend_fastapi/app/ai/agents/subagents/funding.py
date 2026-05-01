from app.ai.utils.markdown import read_markdown_file
from app.ai.tools.search import funding_knowledge_base

def get_funding_subagent_spec() -> dict:
    system_prompt = read_markdown_file("app/ai/prompts/funding.md")
    return {
        "name": "funding-agent",
        "description": "Use for AWS/GCP funding program questions and internal funding KB lookups.",
        "system_prompt": system_prompt,
        "tools": [funding_knowledge_base],
    }


from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable

from app.ai.config import AgentSettings
from app.ai.utils.markdown import read_markdown_file
from app.ai.tools.search import funding_knowledge_base

def get_funding_agent() -> Runnable:
    system_prompt = read_markdown_file("app/ai/prompts/funding_agent.md")
    tools = [funding_knowledge_base]
    config = AgentSettings.funding_agent["agent_config"]
    model = init_chat_model(
        model=config["model"],
        model_provider=config["model_provider"],
        project=config["vertex_project"],
        location=config["vertex_location"],
        temperature=float(config["temperature"]),
        max_output_tokens=int(config["max_output_tokens"]),
    )
    return create_agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
    )






