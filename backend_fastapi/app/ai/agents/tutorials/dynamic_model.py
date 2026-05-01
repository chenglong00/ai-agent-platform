from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from app.ai.tools.math import multiply, add, divide
from app.core.config import settings
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse


tools = [multiply, add, divide]

basic_model = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", 
    temperature=0,
    max_tokens=1000,
    timeout=10,
    api_key=settings.GOOGLE_API_KEY)

advanced_model = ChatGoogleGenerativeAI(
    model="gemini-2.0-pro", 
    temperature=0,
    max_tokens=1000,
    timeout=10,
    api_key=settings.GOOGLE_API_KEY)


@wrap_model_call
def dynamic_model_selection(request: ModelRequest, handler) -> ModelResponse:
    """Choose model based on conversation complexity."""
    message_count = len(request.state["messages"])

    if message_count > 10:
        # Use an advanced model for longer conversations
        model = advanced_model
    else:
        model = basic_model

    return handler(request.override(model=model))


agent = create_agent(
    model=basic_model,  # Default model
    tools=tools,
    middleware=[dynamic_model_selection]
)