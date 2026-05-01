from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from app.ai.tools.math import multiply, add, divide
from app.core.config import settings
from langchain.messages import SystemMessage, HumanMessage

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
    system_prompt="You are a helpful assistant. Be concise and accurate."
)

literary_agent = create_agent(
    model,
    system_prompt=SystemMessage(
        content=[
            {
                "type": "text",
                "text": "You are an AI assistant tasked with analyzing literary works.",
            },
            {
                "type": "text",
                "text": "<the entire contents of 'Pride and Prejudice'>",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    )
)

result = literary_agent.invoke(
    {"messages": [HumanMessage("Analyze the major themes in 'Pride and Prejudice'.")]}
)