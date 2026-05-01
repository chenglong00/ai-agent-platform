from functools import lru_cache

from langchain.chat_models import init_chat_model
from app.ai.tools.math import multiply, add, divide
from langchain.agents import create_agent

@lru_cache(maxsize=1)
def get_base_chat_model():
    """Lazy singleton — Gemini via Google AI (GOOGLE_API_KEY or GEMINI_API_KEY)."""
    model = init_chat_model(
        "gemini-2.0-flash",
        model_provider="google_genai",
        temperature=0,
    )
    tools = [multiply, add, divide]
    return create_agent(
        model=model,
        system_prompt="You are a helpful assistant.",
        tools=tools,
    )