"""Playwright browser tools — each action is a separate tool visible in the chat UI."""

from __future__ import annotations

import base64
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from playwright.async_api import Error as PlaywrightError

from app.ai.chat_agent.playwright_pool import browser_page, invalidate_user_browser
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


def _is_closed_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "closed" in message or "target page" in message


_JQUERY_CONTAINS_RE = re.compile(
    r":contains\(\s*(['\"])(.*?)\1\s*\)",
    re.IGNORECASE,
)


def _normalize_selector(selector: str) -> str:
    """Map jQuery-style :contains() to Playwright's :has-text()."""
    if ":contains(" not in selector.lower():
        return selector
    return _JQUERY_CONTAINS_RE.sub(r':has-text("\2")', selector)


def _locator(page, selector: str):
    """Resolve a Playwright locator from CSS or Playwright selector syntax."""
    sel = selector.strip()
    if sel.lower().startswith("text="):
        return page.locator(sel).first
    if sel.lower().startswith("role="):
        return page.locator(sel).first
    return page.locator(_normalize_selector(sel)).first


async def _page_state_summary(page) -> str:
    title = await page.title()
    url = page.url
    return f"URL: {url}\nTitle: {title}"


async def _run_browser_action(
    user_id: str,
    action: Callable[[Any], Awaitable[str]],
    *,
    log_label: str,
) -> str:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            async with browser_page(user_id) as page:
                return await action(page)
        except PlaywrightError as exc:
            last_error = exc
            if _is_closed_error(exc) and attempt == 0:
                logger.warning(
                    "%s_retry_after_closed user_id=%s attempt=%s",
                    log_label,
                    user_id,
                    attempt + 1,
                )
                await invalidate_user_browser(user_id)
                continue
            logger.exception("%s_failed user_id=%s", log_label, user_id)
            return f"{log_label.replace('_', ' ').title()} failed: {exc}"
        except Exception as exc:
            logger.exception("%s_failed user_id=%s", log_label, user_id)
            return f"{log_label.replace('_', ' ').title()} failed: {exc}"

    if last_error is not None:
        return f"{log_label.replace('_', ' ').title()} failed: {last_error}"
    return f"{log_label.replace('_', ' ').title()} failed: browser unavailable"


@tool
async def browser_goto(url: str, runtime: ToolRuntime) -> str:
    """Open or navigate the browser to a URL (http/https only). Reuses the same browser session for follow-up reads and clicks."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()
    try:
        target = _validate_url(url)
    except ValueError as exc:
        return str(exc)

    user_id = get_user_id_from_run(runtime)

    async def action(page) -> str:
        await page.goto(target, wait_until="domcontentloaded")
        return f"Navigated successfully.\n{await _page_state_summary(page)}"

    return await _run_browser_action(user_id, action, log_label="browser_goto")


@tool
async def browser_read(runtime: ToolRuntime) -> str:
    """Read visible text from the current page. Requires a prior browser_goto in the same turn; the session stays open between browser tools."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    user_id = get_user_id_from_run(runtime)

    async def action(page) -> str:
        body_text = await page.locator("body").inner_text()
        excerpt = _truncate(body_text)
        return f"{await _page_state_summary(page)}\n\nVisible text:\n{excerpt}"

    return await _run_browser_action(user_id, action, log_label="browser_read")


@tool
async def browser_click(selector: str, runtime: ToolRuntime) -> str:
    """Click an element using standard CSS or Playwright selectors (e.g. #id, .class, a:has-text('Sign in')). Do not use jQuery :contains(); use browser_click_text for visible label text instead."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    sel = selector.strip()
    if not sel:
        return "Selector is required."

    user_id = get_user_id_from_run(runtime)

    async def action(page) -> str:
        locator = _locator(page, sel)
        await locator.click(timeout=settings.BROWSER_PLAYWRIGHT_TIMEOUT_MS)
        used = _normalize_selector(sel) if ":contains(" in sel.lower() else sel
        return f"Clicked `{used}`.\n{await _page_state_summary(page)}"

    return await _run_browser_action(user_id, action, log_label="browser_click")


@tool
async def browser_click_text(text: str, runtime: ToolRuntime, exact: bool = False) -> str:
    """Click the first visible element that contains this text (links, buttons, menu items). Use when you know the label but not the CSS selector."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    label = text.strip()
    if not label:
        return "Text is required."

    user_id = get_user_id_from_run(runtime)

    async def action(page) -> str:
        locator = page.get_by_text(label, exact=exact).first
        await locator.click(timeout=settings.BROWSER_PLAYWRIGHT_TIMEOUT_MS)
        return f"Clicked text `{label}`.\n{await _page_state_summary(page)}"

    return await _run_browser_action(user_id, action, log_label="browser_click_text")


@tool
async def browser_click_role(role: str, name: str, runtime: ToolRuntime) -> str:
    """Click by accessibility role and name (e.g. role=link, name=New chat). Prefer for buttons and links when you know the accessible name."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    role_name = role.strip().lower()
    accessible_name = name.strip()
    if not role_name or not accessible_name:
        return "Both role and name are required."

    user_id = get_user_id_from_run(runtime)

    async def action(page) -> str:
        locator = page.get_by_role(role_name, name=accessible_name).first
        await locator.click(timeout=settings.BROWSER_PLAYWRIGHT_TIMEOUT_MS)
        return f"Clicked {role_name} `{accessible_name}`.\n{await _page_state_summary(page)}"

    return await _run_browser_action(user_id, action, log_label="browser_click_role")


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

    async def action(page) -> str:
        locator = _locator(page, sel)
        await locator.fill(text, timeout=settings.BROWSER_PLAYWRIGHT_TIMEOUT_MS)
        if press_enter:
            await locator.press("Enter")
        action_label = "Typed and pressed Enter" if press_enter else "Typed"
        return f"{action_label} into `{sel}`.\n{await _page_state_summary(page)}"

    return await _run_browser_action(user_id, action, log_label="browser_type")


@tool
async def browser_press(key: str, runtime: ToolRuntime) -> str:
    """Press a keyboard key on the page (e.g. Enter, Tab, Escape)."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    key_name = key.strip()
    if not key_name:
        return "Key name is required."

    user_id = get_user_id_from_run(runtime)

    async def action(page) -> str:
        await page.keyboard.press(key_name)
        return f"Pressed {key_name}.\n{await _page_state_summary(page)}"

    return await _run_browser_action(user_id, action, log_label="browser_press")


@tool
async def browser_screenshot(runtime: ToolRuntime) -> str:
    """Capture a screenshot of the current page (also streams a preview to the user)."""
    if not settings.BROWSER_PLAYWRIGHT_ENABLED:
        return _disabled()

    user_id = get_user_id_from_run(runtime)

    async def action(page) -> str:
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

    return await _run_browser_action(user_id, action, log_label="browser_screenshot")


PLAYWRIGHT_BROWSER_TOOLS = [
    browser_goto,
    browser_read,
    browser_click,
    browser_click_text,
    browser_click_role,
    browser_type,
    browser_press,
    browser_screenshot,
]
