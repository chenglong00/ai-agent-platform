"""Per-user Playwright browser pool for chat agent tools."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: dict[str, _UserBrowserSession] = {}
_init_lock = asyncio.Lock()
_frame_subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)


@dataclass
class _UserBrowserSession:
    playwright: Any
    browser: Any
    context: Any
    page: Any
    lock: asyncio.Lock
    last_used_at: float
    loop_id: int
    screencast_active: bool = False
    last_frame_at: float = 0.0


def _current_loop_id() -> int:
    return id(asyncio.get_running_loop())


def _session_alive(session: _UserBrowserSession) -> bool:
    try:
        return bool(session.browser.is_connected())
    except Exception:
        return False


def _session_usable(session: _UserBrowserSession) -> bool:
    if _current_loop_id() != session.loop_id:
        return False
    if not _session_alive(session):
        return False
    try:
        _ = session.page.url
        return True
    except Exception:
        return False


def _min_frame_interval_seconds() -> float:
    fps = max(settings.BROWSER_PLAYWRIGHT_LIVE_MAX_FPS, 1)
    return 1.0 / fps


async def _stop_screencast(session: _UserBrowserSession) -> None:
    if not session.screencast_active:
        return
    try:
        await session.page.screencast.stop()
    except Exception:
        logger.exception("playwright_screencast_stop_failed")
    session.screencast_active = False


async def _close_session(session: _UserBrowserSession) -> None:
    await _stop_screencast(session)
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


def _broadcast_frame(user_id: str, payload: dict[str, Any]) -> None:
    for queue in list(_frame_subscribers.get(user_id, ())):
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass


async def _on_screencast_frame(user_id: str, session: _UserBrowserSession, frame: dict[str, Any]) -> None:
    now = time.monotonic()
    if now - session.last_frame_at < _min_frame_interval_seconds():
        return
    session.last_frame_at = now

    url = ""
    try:
        url = session.page.url
    except Exception:
        pass

    _broadcast_frame(
        user_id,
        {
            "type": "browser_frame",
            "image_base64": base64.b64encode(frame["data"]).decode("ascii"),
            "url": url,
            "viewport_width": frame.get("viewportWidth"),
            "viewport_height": frame.get("viewportHeight"),
        },
    )


async def _ensure_screencast(user_id: str, session: _UserBrowserSession) -> None:
    if not settings.BROWSER_PLAYWRIGHT_LIVE_ENABLED:
        return
    if session.screencast_active:
        return

    async def on_frame(frame: dict[str, Any]) -> None:
        await _on_screencast_frame(user_id, session, frame)

    await session.page.screencast.start(
        on_frame=on_frame,
        quality=settings.BROWSER_PLAYWRIGHT_LIVE_JPEG_QUALITY,
    )
    session.screencast_active = True
    logger.info("playwright_screencast_started user_id=%s", user_id)


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
    session = _UserBrowserSession(
        playwright=playwright,
        browser=browser,
        context=context,
        page=page,
        lock=asyncio.Lock(),
        last_used_at=time.monotonic(),
        loop_id=_current_loop_id(),
    )
    logger.info("playwright_session_created user_id=%s loop_id=%s", user_id, session.loop_id)
    await _ensure_screencast(user_id, session)
    return session


async def _remove_stale_session(user_id: str, session: _UserBrowserSession) -> None:
    key = str(user_id)
    async with _init_lock:
        if _pool.get(key) is session:
            _pool.pop(key, None)
    await _close_session(session)
    logger.info("playwright_session_stale_removed user_id=%s", key)


async def invalidate_user_browser(user_id: str) -> None:
    """Force-close a user's browser session so the next tool call creates a fresh one."""
    await release_user_browser(user_id)


async def _get_or_create_session(user_id: str) -> _UserBrowserSession:
    key = str(user_id)
    async with _init_lock:
        session = _pool.get(key)
        if session is not None and not _session_usable(session):
            _pool.pop(key, None)
            stale = session
        else:
            stale = None

    if stale is not None:
        await _close_session(stale)
        logger.info("playwright_session_replaced_unusable user_id=%s", key)

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
            if current is not session or not _session_usable(session):
                if attempt == 0:
                    await _remove_stale_session(key, session)
                    continue
                msg = "Browser session is unavailable"
                raise RuntimeError(msg)

            session.last_used_at = time.monotonic()
            await _ensure_screencast(key, session)
            try:
                yield session.page
            except Exception:
                if not _session_usable(session):
                    await _remove_stale_session(key, session)
                raise
            return

    msg = "Browser session could not be established"
    raise RuntimeError(msg)


async def subscribe_browser_frames(user_id: str) -> AsyncIterator[dict[str, Any]]:
    """Yield screencast frames for a user until the subscriber disconnects."""
    key = str(user_id)
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2)
    _frame_subscribers[key].add(queue)
    logger.info("playwright_live_subscriber_added user_id=%s", key)
    try:
        yield {"type": "browser_live_ready"}
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=30.0)
            except TimeoutError:
                yield {"type": "browser_live_ping"}
                continue
            yield frame
    finally:
        _frame_subscribers[key].discard(queue)
        if not _frame_subscribers[key]:
            _frame_subscribers.pop(key, None)
        logger.info("playwright_live_subscriber_removed user_id=%s", key)


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
    expired: list[tuple[str, _UserBrowserSession]] = []
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
