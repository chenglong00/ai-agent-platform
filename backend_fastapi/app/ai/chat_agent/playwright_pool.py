"""Per-user Playwright browser pool for chat agent tools."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: dict[str, _UserBrowserSession] = {}
_init_lock = asyncio.Lock()


@dataclass
class _UserBrowserSession:
    playwright: Any
    browser: Any
    context: Any
    page: Any
    lock: asyncio.Lock
    last_used_at: float


async def _create_session(user_id: str) -> _UserBrowserSession:
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=settings.BROWSER_PLAYWRIGHT_HEADLESS)
    context = await browser.new_context(
        viewport={
            "width": settings.BROWSER_PLAYWRIGHT_VIEWPORT_WIDTH,
            "height": settings.BROWSER_PLAYWRIGHT_VIEWPORT_HEIGHT,
        },
    )
    page = await context.new_page()
    page.set_default_timeout(settings.BROWSER_PLAYWRIGHT_TIMEOUT_MS)
    logger.info("playwright_session_created user_id=%s", user_id)
    return _UserBrowserSession(
        playwright=playwright,
        browser=browser,
        context=context,
        page=page,
        lock=asyncio.Lock(),
        last_used_at=time.monotonic(),
    )


async def get_browser_page(user_id: str) -> tuple[Any, asyncio.Lock]:
    """Return (page, lock) for a user, creating a session if needed."""
    key = str(user_id)
    async with _init_lock:
        session = _pool.get(key)
        if session is None:
            session = await _create_session(key)
            _pool[key] = session
        session.last_used_at = time.monotonic()
        return session.page, session.lock


async def release_user_browser(user_id: str) -> None:
    """Close and remove a user's Playwright session."""
    key = str(user_id)
    async with _init_lock:
        session = _pool.pop(key, None)
    if session is None:
        return
    try:
        await session.context.close()
        await session.browser.close()
        await session.playwright.stop()
        logger.info("playwright_session_released user_id=%s", key)
    except Exception:
        logger.exception("playwright_session_release_failed user_id=%s", key)


async def shutdown_all_browsers() -> None:
    """Close every pooled Playwright session."""
    async with _init_lock:
        sessions = list(_pool.items())
        _pool.clear()
    for user_id, session in sessions:
        try:
            await session.context.close()
            await session.browser.close()
            await session.playwright.stop()
            logger.info("playwright_session_shutdown user_id=%s", user_id)
        except Exception:
            logger.exception("playwright_session_shutdown_failed user_id=%s", user_id)


async def cleanup_idle_browsers() -> int:
    """Release sessions idle longer than the configured TTL."""
    ttl = settings.BROWSER_PLAYWRIGHT_IDLE_TTL_SECONDS
    if ttl <= 0:
        return 0

    now = time.monotonic()
    expired: list[str] = []
    async with _init_lock:
        for user_id, session in _pool.items():
            if now - session.last_used_at > ttl:
                expired.append(user_id)

    for user_id in expired:
        await release_user_browser(user_id)
        logger.info("playwright_session_idle_expired user_id=%s ttl_s=%s", user_id, ttl)
    return len(expired)
