"""Per-user Playwright browser pool for chat agent tools."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

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


def _session_alive(session: _UserBrowserSession) -> bool:
    try:
        return bool(session.browser.is_connected())
    except Exception:
        return False


async def _close_session(session: _UserBrowserSession) -> None:
    try:
        await session.context.close()
    except Exception:
        pass
    try:
        await session.browser.close()
    except Exception:
        pass
    try:
        await session.playwright.stop()
    except Exception:
        pass


async def _create_session(user_id: str) -> _UserBrowserSession:
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    launch_kwargs: dict[str, Any] = {"headless": settings.BROWSER_PLAYWRIGHT_HEADLESS}
    if settings.BROWSER_PLAYWRIGHT_HEADLESS:
        launch_kwargs["args"] = ["--no-sandbox"]
    browser = await playwright.chromium.launch(**launch_kwargs)
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


async def _remove_stale_session(user_id: str, session: _UserBrowserSession) -> None:
    key = str(user_id)
    async with _init_lock:
        if _pool.get(key) is session:
            _pool.pop(key, None)
    await _close_session(session)
    logger.info("playwright_session_stale_removed user_id=%s", key)


async def _get_or_create_session(user_id: str) -> _UserBrowserSession:
    key = str(user_id)
    async with _init_lock:
        session = _pool.get(key)
        if session is not None and not _session_alive(session):
            _pool.pop(key, None)
            stale = session
        else:
            stale = None

    if stale is not None:
        await _close_session(stale)
        logger.info("playwright_session_replaced_dead user_id=%s", key)

    async with _init_lock:
        session = _pool.get(key)
        if session is None:
            session = await _create_session(key)
            _pool[key] = session
        session.last_used_at = time.monotonic()
        return session


@asynccontextmanager
async def browser_page(user_id: str) -> AsyncIterator[Any]:
    """Yield a live page, holding the per-user lock for the whole operation."""
    key = str(user_id)
    for attempt in range(2):
        session = await _get_or_create_session(key)
        async with session.lock:
            current = _pool.get(key)
            if current is not session or not _session_alive(session):
                if attempt == 0:
                    await _remove_stale_session(key, session)
                    continue
                msg = "Browser session is unavailable"
                raise RuntimeError(msg)

            session.last_used_at = time.monotonic()
            try:
                yield session.page
            except Exception:
                if not _session_alive(session):
                    await _remove_stale_session(key, session)
                raise
            return

    msg = "Browser session could not be established"
    raise RuntimeError(msg)


async def release_user_browser(user_id: str) -> None:
    """Close and remove a user's Playwright session after in-flight work finishes."""
    key = str(user_id)
    async with _init_lock:
        session = _pool.get(key)
    if session is None:
        return

    async with session.lock:
        async with _init_lock:
            if _pool.get(key) is session:
                _pool.pop(key, None)
        await _close_session(session)
        logger.info("playwright_session_released user_id=%s", key)


async def shutdown_all_browsers() -> None:
    """Close every pooled Playwright session."""
    async with _init_lock:
        sessions = list(_pool.items())
        _pool.clear()

    for user_id, session in sessions:
        async with session.lock:
            try:
                await _close_session(session)
                logger.info("playwright_session_shutdown user_id=%s", user_id)
            except Exception:
                logger.exception("playwright_session_shutdown_failed user_id=%s", user_id)


async def cleanup_idle_browsers() -> int:
    """Release sessions idle longer than the configured TTL."""
    ttl = settings.BROWSER_PLAYWRIGHT_IDLE_TTL_SECONDS
    if ttl <= 0:
        return 0

    now = time.monotonic()
    expired: list[_UserBrowserSession] = []
    async with _init_lock:
        for user_id, session in list(_pool.items()):
            if now - session.last_used_at > ttl:
                expired.append((user_id, session))

    removed = 0
    for user_id, session in expired:
        async with session.lock:
            async with _init_lock:
                if _pool.get(str(user_id)) is not session:
                    continue
                _pool.pop(str(user_id), None)
            await _close_session(session)
            removed += 1
            logger.info("playwright_session_idle_expired user_id=%s ttl_s=%s", user_id, ttl)
    return removed
