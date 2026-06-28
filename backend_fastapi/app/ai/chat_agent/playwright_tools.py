"""Playwright browser tools — each action is a separate tool visible in the chat UI."""

from __future__ import annotations

import base64
import logging
from urllib.parse import urlparse

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.ai.chat_agent.playwright_pool import get_browser_page, release_user_browser
from app.ai.chat_agent.run_context import get_user_id_from_run
from app.core.config import settings

logger = logging.getLogger(__name__)


def _disabled() -> str:
    return "Browser automation is disabled on this server."


def _validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        msg = "URL must start with http:// or https://"
        raise ValueError(msg)
    return url.strip()


def _truncate(text: str, limit: int | None = None) -> str:
    cap = limit or settings.BROWSER_PLAYWRIGHT_READ_MAX_CHARS
    cleaned = " ".join(text.split())
    if len(cleaned) <= cap:
        return cleaned
    return cleaned[: cap - 3] + "..."


async def _page_state_summary(page) -> str:
    title = await page.title()
    url = page.url
    return f"URL: {url}\nTitle: {title}"


@tool
async def browser_goto(url: str, runtime: ToolRuntime) -> str:
    """Open or navigate the browser to a URL (http/https only)."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()
    try:
        target = _validate_url(url)
    except ValueError as exc:
        return str(exc)

    user_id = get_user_id_from_run(runtime)
    page, lock = await get_browser_page(user_id)
    async with lock:
        try:
            await page.goto(target, wait_until="domcontentloaded")
            return f"Navigated successfully.\n{await _page_state_summary(page)}"
        except Exception as exc:
            logger.exception("browser_goto_failed user_id=%s url=%s", user_id, target)
            return f"Navigation failed: {exc}"


@tool
async def browser_read(runtime: ToolRuntime) -> str:
    """Read visible text from the current page to decide the next browser action."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    user_id = get_user_id_from_run(runtime)
    page, lock = await get_browser_page(user_id)
    async with lock:
        try:
            body_text = await page.locator("body").inner_text()
            excerpt = _truncate(body_text)
            return f"{await _page_state_summary(page)}\n\nVisible text:\n{excerpt}"
        except Exception as exc:
            logger.exception("browser_read_failed user_id=%s", user_id)
            return f"Could not read page: {exc}"


@tool
async def browser_click(selector: str, runtime: ToolRuntime) -> str:
    """Click an element on the page using a CSS selector."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    sel = selector.strip()
    if not sel:
        return "Selector is required."

    user_id = get_user_id_from_run(runtime)
    page, lock = await get_browser_page(user_id)
    async with lock:
        try:
            await page.locator(sel).first.click(timeout=settings.BROWSER_PLAYWRIGHT_TIMEOUT_MS)
            return f"Clicked `{sel}`.\n{await _page_state_summary(page)}"
        except Exception as exc:
            logger.exception("browser_click_failed user_id=%s selector=%s", user_id, sel)
            return f"Click failed on `{sel}`: {exc}"


@tool
async def browser_type(
    selector: str,
    text: str,
    runtime: ToolRuntime,
    press_enter: bool = False,
) -> str:
    """Type text into an input field matched by CSS selector. Set press_enter=true to submit."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    sel = selector.strip()
    if not sel:
        return "Selector is required."

    user_id = get_user_id_from_run(runtime)
    page, lock = await get_browser_page(user_id)
    async with lock:
        try:
            locator = page.locator(sel).first
            await locator.fill(text, timeout=settings.BROWSER_PLAYWRIGHT_TIMEOUT_MS)
            if press_enter:
                await locator.press("Enter")
            action = "Typed and pressed Enter" if press_enter else "Typed"
            return f"{action} into `{sel}`.\n{await _page_state_summary(page)}"
        except Exception as exc:
            logger.exception("browser_type_failed user_id=%s selector=%s", user_id, sel)
            return f"Type failed on `{sel}`: {exc}"


@tool
async def browser_press(key: str, runtime: ToolRuntime) -> str:
    """Press a keyboard key on the page (e.g. Enter, Tab, Escape)."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    key_name = key.strip()
    if not key_name:
        return "Key name is required."

    user_id = get_user_id_from_run(runtime)
    page, lock = await get_browser_page(user_id)
    async with lock:
        try:
            await page.keyboard.press(key_name)
            return f"Pressed {key_name}.\n{await _page_state_summary(page)}"
        except Exception as exc:
            logger.exception("browser_press_failed user_id=%s key=%s", user_id, key_name)
            return f"Key press failed: {exc}"


@tool
async def browser_screenshot(runtime: ToolRuntime) -> str:
    """Capture a screenshot of the current page (also streams a preview to the user)."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    user_id = get_user_id_from_run(runtime)
    page, lock = await get_browser_page(user_id)
    async with lock:
        try:
            png = await page.screenshot(type="png", full_page=False)
            encoded = base64.b64encode(png).decode("ascii")
            runtime.emit_output_delta(
                {
                    "type": "screenshot",
                    "url": page.url,
                    "image_base64": encoded,
                },
            )
            return f"Screenshot captured.\n{await _page_state_summary(page)}"
        except Exception as exc:
            logger.exception("browser_screenshot_failed user_id=%s", user_id)
            return f"Screenshot failed: {exc}"


@tool
async def browser_close(runtime: ToolRuntime) -> str:
    """Close the browser session for this user when finished browsing."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    user_id = get_user_id_from_run(runtime)
    await release_user_browser(user_id)
    return "Browser session closed."


PLAYWRIGHT_BROWSER_TOOLS = [
    browser_goto,
    browser_read,
    browser_click,
    browser_type,
    browser_press,
    browser_screenshot,
    browser_close,
]
