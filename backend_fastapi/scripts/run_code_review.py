"""Standalone runner for the code_review_agent.

Usage:
    python scripts/run_code_review.py <path-to-file-or-directory> [optional question]

Examples:
    python scripts/run_code_review.py app/ai/tools/math.py
    python scripts/run_code_review.py app/api/v1/chat.py "focus on security issues"
    python scripts/run_code_review.py app/ai/tools/ "list all files then review each one"

The script must be run from the backend_fastapi/ directory so that app.* imports resolve.
"""

import asyncio
import sys
from pathlib import Path

# ── Make sure `app.*` imports work when run from backend_fastapi/ ─────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from app.ai.agents.code_review_agent import get_code_review_agent  # noqa: E402


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
        print(__doc__)
        sys.exit(1)

    target = sys.argv[1]
    extra = sys.argv[2] if len(sys.argv) > 2 else ""

    user_message = f"Please review: {target}"
    if extra:
        user_message += f"\n\nFocus: {extra}"

    print(f"\n🔍  Reviewing: {target}\n{'─' * 60}")

    agent = get_code_review_agent()
    result = await agent.ainvoke({"messages": [HumanMessage(content=user_message)]})

    print(_extract_text(result))


if __name__ == "__main__":
    asyncio.run(main())
