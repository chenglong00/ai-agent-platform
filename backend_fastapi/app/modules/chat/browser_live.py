"""WebSocket live view for Playwright browser sessions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.ai.chat_agent.playwright_pool import subscribe_browser_frames
from app.core.config import settings
from app.core.db.postgres import get_async_session_factory
from app.modules.auth.dependencies import get_user_from_token

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/browser/live")
async def browser_live(websocket: WebSocket, token: str = Query(...)) -> None:
    """Stream JPEG screencast frames for the authenticated user's browser session."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Browser disabled")
        return
    if not settings.BROWSER_PLAYWRIGHT_LIVE_ENABLED:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Live view disabled")
        return

    token_value = token.strip()
    if not token_value:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return

    factory = get_async_session_factory()
    async with factory() as session:
        try:
            user = await get_user_from_token(session, token_value)
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
            return

    await websocket.accept()
    user_id = str(user.id)
    logger.info("browser_live_connected user_id=%s", user_id)

    try:
        async for event in subscribe_browser_frames(user_id):
            if event.get("type") == "browser_frame":
                await websocket.send_json(event)
            elif event.get("type") == "browser_live_ready":
                await websocket.send_json(event)
            elif event.get("type") == "browser_live_ping":
                await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info("browser_live_disconnected user_id=%s", user_id)
    except Exception:
        logger.exception("browser_live_stream_failed user_id=%s", user_id)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
