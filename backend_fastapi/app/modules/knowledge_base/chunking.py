"""PDF text extraction and chunking strategies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.modules.knowledge_base.schema import ChunkingStrategyId, PagePreview, ParsingStrategyId


@dataclass
class TextChunk:
    index: int
    text: str
    page: int | None = None


def extract_pdf_pages(path: Path) -> list[PagePreview]:
    reader = PdfReader(str(path))
    pages: list[PagePreview] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append(PagePreview(page=i, text=text))
    return pages


async def extract_pdf_pages_async(
    path: Path,
    strategy: ParsingStrategyId = "pypdf",
) -> list[PagePreview]:
    if strategy == "gemini":
        from app.modules.knowledge_base.gemini_extraction import extract_pdf_pages_gemini

        return await extract_pdf_pages_gemini(path)
    return extract_pdf_pages(path)


def chunk_pages(
    pages: list[PagePreview],
    strategy: ChunkingStrategyId,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[TextChunk]:
    if strategy == "by_page":
        chunks: list[TextChunk] = []
        for i, page in enumerate(pages):
            text = page.text.strip()
            if not text:
                continue
            chunks.append(TextChunk(index=len(chunks), text=text, page=page.page))
        return chunks

    full_text = "\n\n".join(p.text for p in pages if p.text.strip())
    if not full_text.strip():
        return []

    if strategy == "fixed_size":
        splitter = CharacterTextSplitter(
            separator="\n\n",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

    parts = splitter.split_text(full_text)
    return [TextChunk(index=i, text=part) for i, part in enumerate(parts) if part.strip()]
