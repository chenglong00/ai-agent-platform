from langchain.agents.structured_output import ProviderStrategy
from langchain.agents import create_agent
from app.ai.tools.math import multiply, add, divide

tools = [multiply, add, divide]

# ProviderStrategy uses the model provider’s native structured output generation. This is more reliable but only works with providers that support native structured output:
from pydantic import BaseModel

class ContactInfo(BaseModel):
    name: str
    email: str
    phone: str

agent = create_agent(
    model="gpt-4.1",
    response_format=ProviderStrategy(ContactInfo)
)