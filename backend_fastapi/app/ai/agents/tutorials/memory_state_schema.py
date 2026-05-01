from langchain.agents import AgentState, create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from app.ai.tools.math import multiply, add, divide
from app.core.config import settings    


tools = [multiply, add, divide]
model = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
    max_tokens=1000,
    timeout=10,
    api_key=settings.GOOGLE_API_KEY)
# Use the state_schema parameter as a shortcut to define custom state that is only used in tools.


class CustomState(AgentState):
    user_preferences: dict

agent = create_agent(
    model,
    tools=tools,
    state_schema=CustomState
)
# The agent can now track additional state beyond messages
result = agent.invoke({
    "messages": [{"role": "user", "content": "I prefer technical explanations"}],
    "user_preferences": {"style": "technical", "verbosity": "detailed"},
})