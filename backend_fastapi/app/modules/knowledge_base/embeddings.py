"""Embedding model registry and batch embedding."""

from __future__ import annotations

import logging
from typing import Sequence

from langchain_google_vertexai import VertexAIEmbeddings

from app.ai.config import AgentSettings
from app.modules.knowledge_base.schema import EmbeddingModelId, EmbeddingModelOption

logger = logging.getLogger(__name__)

EMBEDDING_MODELS: list[EmbeddingModelOption] = [
    EmbeddingModelOption(
        id="text-embedding-004",
        label="Vertex — text-embedding-004",
        description="Google's latest general-purpose embedding model (recommended).",
        dimensions=768,
    ),
    EmbeddingModelOption(
        id="text-embedding-005",
        label="Vertex — text-embedding-005",
        description="Higher-quality embeddings for retrieval-heavy workloads.",
        dimensions=768,
    ),
    EmbeddingModelOption(
        id="textembedding-gecko@003",
        label="Vertex — textembedding-gecko@003",
        description="Legacy Gecko model; use text-embedding-004 for new projects.",
        dimensions=768,
    ),
]


def _vertex_config() -> tuple[str, str]:
    cfg = AgentSettings.deep_agent.get("agent_config", {})
    project = str(cfg.get("vertex_project") or "").strip()
    location = str(cfg.get("vertex_location") or "us-central1").strip()
    return project, location


def get_embeddings(model_id: EmbeddingModelId) -> VertexAIEmbeddings:
    project, location = _vertex_config()
    if not project:
        raise ValueError(
            "Vertex project is not configured. Set vertex_project in agent config "
            "or configure GCP credentials for embeddings."
        )
    return VertexAIEmbeddings(
        model_name=model_id,
        project=project,
        location=location,
    )


async def embed_texts(model_id: EmbeddingModelId, texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []
    embedder = get_embeddings(model_id)
    try:
        vectors = await embedder.aembed_documents(list(texts))
    except Exception:
        logger.exception("embedding_failed model=%s count=%s", model_id, len(texts))
        raise
    return vectors
