from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import AgentMiddleware
from typing import Any
from app.ai.tools.math import multiply, add, divide
from app.core.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI


# Use middleware to define custom state when your custom state 
# needs to be accessed by specific middleware hooks and 
# tools attached to said middleware.



tools = [multiply, add, divide]
model = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
    max_tokens=1000,
    timeout=10,
    api_key=settings.GOOGLE_API_KEY)

class CustomState(AgentState):
    # already contains messages, tools, etc.
    user_preferences: dict

class CustomMiddleware(AgentMiddleware):
    state_schema = CustomState
    tools = tools

    def before_model(self, state: CustomState, runtime) -> dict[str, Any] | None:
        return state.user_preferences # return the user preferences to the model    

agent = create_agent(
    model,
    tools=tools,
    middleware=[CustomMiddleware()]
)

# The agent can now track additional state beyond messages
result = agent.invoke({
    "messages": [{"role": "user", "content": "I prefer technical explanations"}],
    "user_preferences": {"style": "technical", "verbosity": "detailed"},
})