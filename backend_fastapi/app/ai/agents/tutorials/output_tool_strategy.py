from pydantic import BaseModel
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from app.ai.tools.math import multiply, add, divide
tools = [multiply, add, divide]

class ContactInfo(BaseModel):
    name: str
    email: str
    phone: str

# ToolStrategy uses artificial tool calling to generate structured output. This works with any model that supports tool calling. ToolStrategy should be used when provider-native structured output (via ProviderStrategy) is not available or reliable.


agent = create_agent(
    model="gemini-2.0-flash",
    tools=tools,
    response_format=ToolStrategy(ContactInfo)
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "Extract contact info from: John Doe, john@example.com, (555) 123-4567"}]
})

result["structured_response"]
# ContactInfo(name='John Doe', email='john@example.com', phone='(555) 123-4567')