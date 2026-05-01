"""Static models are configured once when creating the agent and remain unchanged throughout execution. This is the most common and straightforward approach.
"""

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from app.ai.tools.math import multiply, add, divide
from app.core.config import settings

# static tools
tools = [multiply, add, divide]

# Simple
# agent = create_agent("gemini-2.0-flash", tools=tools)

# OR more control
model = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", 
    temperature=0,
    max_tokens=1000,
    timeout=10,
    api_key=settings.GOOGLE_API_KEY)

agent = create_agent(model, tools=tools)