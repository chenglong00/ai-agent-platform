"""Vector similarity search over ingested knowledge base chunks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KnowledgeSearchHit:
    document_id: str
    document_title: str
    page: int | None
    chunk_index: int
    score: float
    text: str


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_chunks(
    query_vector: list[float],
    chunks: list[dict[str, Any]],
    *,
    top_k: int,
    min_score: float,
) -> list[KnowledgeSearchHit]:
    scored: list[KnowledgeSearchHit] = []
    for chunk in chunks:
        embedding = chunk.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            continue
        score = cosine_similarity(query_vector, embedding)
        if score < min_score:
            continue
        meta = chunk.get("meta") if isinstance(chunk.get("meta"), dict) else {}
        title = str(meta.get("title") or "Untitled document")
        scored.append(
            KnowledgeSearchHit(
                document_id=str(chunk.get("document_id") or ""),
                document_title=title,
                page=chunk.get("page"),
                chunk_index=int(chunk.get("index", 0)),
                score=score,
                text=str(chunk.get("text") or ""),
            ),
        )
    scored.sort(key=lambda hit: hit.score, reverse=True)
    return scored[:top_k]
