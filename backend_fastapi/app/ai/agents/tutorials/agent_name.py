from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from app.ai.tools.math import multiply, add, divide
from app.core.config import settings

# Set an optional name for the agent. This is used as the node identifier when adding the agent as a subgraph in multi-agent systems:

tools = [multiply, add, divide]
model = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
    max_tokens=1000,
    timeout=10,
    api_key=settings.GOOGLE_API_KEY)

agent = create_agent(
    model,
    tools,
    name="research_assistant"
)