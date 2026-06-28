"""Gemini-based PDF text extraction via Vertex AI."""

from __future__ import annotations

import base64
import json
import logging
import re
from io import BytesIO
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI
from pypdf import PdfReader, PdfWriter

from app.ai.config import AgentSettings
from app.core.config import settings
from app.modules.knowledge_base.schema import PagePreview

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _vertex_config() -> tuple[str, str, str]:
    cfg = AgentSettings.deep_agent.get("agent_config", {})
    project = str(cfg.get("vertex_project") or "").strip()
    location = str(cfg.get("vertex_location") or "us-central1").strip()
    model = str(cfg.get("model") or "gemini-2.5-flash").strip()
    return project, location, model


def _chat_model() -> ChatVertexAI:
    project, location, model = _vertex_config()
    if not project:
        raise ValueError(
            "Vertex project is not configured. Set vertex_project in agent config "
            "or configure GCP credentials for Gemini PDF parsing."
        )
    return ChatVertexAI(
        model_name=model,
        project=project,
        location=location,
        temperature=0,
        max_output_tokens=8192,
    )


def _pdf_bytes_for_page_range(path: Path, page_start: int, page_end: int) -> bytes:
    reader = PdfReader(str(path))
    writer = PdfWriter()
    for page_index in range(page_start - 1, page_end):
        if page_index < len(reader.pages):
            writer.add_page(reader.pages[page_index])
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _parse_json_payload(raw: str) -> dict:
    text = raw.strip()
    if not text:
        raise ValueError("Gemini returned an empty response.")
    match = _JSON_BLOCK_RE.search(text)
    if match:
        text = match.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini response was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Gemini response JSON must be an object.")
    return payload


def _pages_from_payload(payload: dict, page_start: int, page_end: int) -> list[PagePreview]:
    raw_pages = payload.get("pages")
    if not isinstance(raw_pages, list):
        raise ValueError('Gemini response must include a "pages" array.')

    parsed: dict[int, str] = {}
    for item in raw_pages:
        if not isinstance(item, dict):
            continue
        page_num = item.get("page")
        text = item.get("text")
        if not isinstance(page_num, int):
            continue
        if page_start <= page_num <= page_end:
            parsed[page_num] = str(text or "").strip()

    return [
        PagePreview(page=page_num, text=parsed.get(page_num, ""))
        for page_num in range(page_start, page_end + 1)
    ]


def _extraction_prompt(page_start: int, page_end: int) -> str:
    return (
        "Extract all readable text from this PDF as clean markdown. "
        "Preserve headings, lists, tables, and reading order. "
        "Do not summarize, translate, or add commentary. "
        "Return ONLY valid JSON with this exact shape:\n"
        '{"pages":[{"page":<number>,"text":"<extracted markdown>"}]}\n'
        f"Include one entry per page from {page_start} through {page_end}. "
        "Use empty string for pages with no readable text."
    )


async def _extract_pdf_batch(path: Path, page_start: int, page_end: int) -> list[PagePreview]:
    pdf_bytes = _pdf_bytes_for_page_range(path, page_start, page_end)
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    message = HumanMessage(
        content=[
            {"type": "media", "mime_type": "application/pdf", "data": pdf_b64},
            {"type": "text", "text": _extraction_prompt(page_start, page_end)},
        ],
    )
    model = _chat_model()
    response = await model.ainvoke([message])
    content = response.content
    if isinstance(content, list):
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        raw = "\n".join(part for part in text_parts if part)
    else:
        raw = str(content or "")
    payload = _parse_json_payload(raw)
    return _pages_from_payload(payload, page_start, page_end)


async def extract_pdf_pages_gemini(path: Path) -> list[PagePreview]:
    """Extract PDF text page-by-page using Gemini multimodal parsing."""
    if not settings.KNOWLEDGE_BASE_GEMINI_PARSING_ENABLED:
        raise ValueError("Gemini PDF parsing is disabled on this server.")

    reader = PdfReader(str(path))
    total_pages = len(reader.pages)
    if total_pages == 0:
        return []

    batch_size = max(1, settings.KNOWLEDGE_BASE_GEMINI_PARSING_BATCH_PAGES)
    pages: list[PagePreview] = []

    for page_start in range(1, total_pages + 1, batch_size):
        page_end = min(page_start + batch_size - 1, total_pages)
        logger.info(
            "gemini_pdf_extract path=%s pages=%s-%s",
            path.name,
            page_start,
            page_end,
        )
        batch_pages = await _extract_pdf_batch(path, page_start, page_end)
        pages.extend(batch_pages)

    return pages
