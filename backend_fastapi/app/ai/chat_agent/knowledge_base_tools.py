"""Knowledge base RAG tools for the chat agent."""

from __future__ import annotations

import logging

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.ai.chat_agent.run_context import get_user_access_context_from_run
from app.core.config import settings
from app.modules.knowledge_base.client import get_mongodb
from app.modules.knowledge_base.search import KnowledgeSearchHit
from app.modules.knowledge_base.service import knowledge_base_service

logger = logging.getLogger(__name__)


def _format_hits(hits: list[KnowledgeSearchHit]) -> str:
    parts: list[str] = [f"Found {len(hits)} relevant excerpt(s):\n"]
    for idx, hit in enumerate(hits, start=1):
        page = f", page {hit.page}" if hit.page is not None else ""
        parts.append(
            f"[{idx}] {hit.document_title} (score {hit.score:.2f}{page})\n{hit.text.strip()}\n",
        )
    return "\n".join(parts).strip()


@tool
async def search_knowledge_base(query: str, runtime: ToolRuntime) -> str:
    """Search ingested knowledge base documents for excerpts relevant to a question. Use for internal docs, uploaded PDFs, policies, and reference material."""
    if not settings.KNOWLEDGE_BASE_RAG_ENABLED:
        return "Knowledge base search is disabled on this server."

    q = query.strip()
    if not q:
        return "Provide a search query."

    try:
        get_mongodb()
    except RuntimeError:
        return (
            "Knowledge base is not available (MongoDB is not configured). "
            "Upload and ingest documents in the Knowledge Base UI first."
        )

    try:
        ctx = get_user_access_context_from_run(runtime)
        hits = await knowledge_base_service.search(ctx, q)
    except ValueError as exc:
        return str(exc)
    except Exception:
        logger.exception("search_knowledge_base_failed query=%s", q)
        return "Knowledge base search failed due to a server error."

    if not hits:
        return (
            "No relevant knowledge base excerpts found. "
            "The user may need to upload and ingest PDFs in Knowledge Base first."
        )
    return _format_hits(hits)
