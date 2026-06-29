"""Resolve remote agents via the A2A Agent Card protocol."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
from a2a.client.card_resolver import A2ACardResolver, AgentCardResolutionError
from google.protobuf.json_format import MessageToDict

_AGENT_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def normalize_agent_url(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("Agent URL is required")
    if not _AGENT_URL_RE.match(value):
        raise ValueError("Agent URL must start with http:// or https://")
    parsed = urlparse(value)
    if not parsed.netloc:
        raise ValueError("Agent URL is invalid")
    return value.rstrip("/")


async def fetch_agent_card(agent_url: str) -> dict[str, Any]:
    """Fetch and validate an A2A Agent Card from a remote agent base URL."""
    base_url = normalize_agent_url(agent_url)
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resolver = A2ACardResolver(client, base_url)
        try:
            card = await resolver.get_agent_card()
        except AgentCardResolutionError as exc:
            raise ValueError(str(exc)) from exc
    return MessageToDict(card, preserving_proto_field_name=False)


def card_display_name(card: dict[str, Any], override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    name = str(card.get("name") or "").strip()
    return name or "Remote agent"


def card_display_description(card: dict[str, Any], override: str | None = None) -> str:
    if override is not None and override.strip():
        return override.strip()
    return str(card.get("description") or "").strip()


def card_skills(card: dict[str, Any]) -> list[dict[str, Any]]:
    raw = card.get("skills")
    if not isinstance(raw, list):
        return []
    skills: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        skills.append(item)
    return skills
