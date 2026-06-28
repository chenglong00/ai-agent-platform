"""Standalone runner for the chat deep agent.

Usage:
    python scripts/run_code_review.py "check whether the agent works"
"""

import asyncio
import sys
from pathlib import Path

# ── Make sure `app.*` imports work when run from backend_fastapi/ ─────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from app.ai.chat_agent.graph import get_deep_agent  # noqa: E402


def _extract_text(result: object) -> str:
    """Pull assistant text out of whatever create_agent returns."""
    if isinstance(result, AIMessage):
        c = result.content
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return "\n".join(
                item["text"] if isinstance(item, dict) else str(item)
                for item in c
                if not isinstance(item, dict) or item.get("text")
            )
    if isinstance(result, dict):
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                return _extract_text(msg)
    return str(result)


async def main() -> None:
    if len(sys.argv) < 2:
        user_message = "What's the weather in Singapore?"
    else:
        user_message = " ".join(sys.argv[1:])

    agent = get_deep_agent()
    result = await agent.ainvoke({"messages": [HumanMessage(content=user_message)]})

    print(_extract_text(result))


if __name__ == "__main__":
    asyncio.run(main())
