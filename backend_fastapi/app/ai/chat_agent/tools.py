"""Tools for the chat deep agent."""

import httpx
from langchain_core.tools import tool


@tool
def check_weather(location: str) -> str:
    """Get current weather for a city or location (e.g. 'Singapore', 'London')."""
    loc = location.strip()
    if not loc:
        return "Please provide a location, e.g. Singapore or London."

    url = f"https://wttr.in/{loc.replace(' ', '+')}?format=3"
    try:
        response = httpx.get(
            url,
            timeout=10.0,
            headers={"User-Agent": "curl/8.0"},
        )
        response.raise_for_status()
        return response.text.strip()
    except httpx.HTTPError as exc:
        return f"Could not fetch weather for {loc}: {exc}"
