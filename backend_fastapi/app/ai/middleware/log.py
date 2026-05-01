import logging

from langchain.agents.middleware import wrap_tool_call

logger = logging.getLogger(__name__)
call_count = [0]


@wrap_tool_call
async def log_tool_calls(request, handler):
    """Log every tool call — async so it works with ainvoke/astream."""
    call_count[0] += 1
    tool_name = request.name if hasattr(request, "name") else str(request)
    args = request.args if hasattr(request, "args") else "N/A"

    logger.info("[Middleware] Tool call #%d: %s  args=%s", call_count[0], tool_name, args)

    result = await handler(request)

    logger.info("[Middleware] Tool call #%d completed", call_count[0])
    return result
