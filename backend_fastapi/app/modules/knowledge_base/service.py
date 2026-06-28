"""Knowledge base persistence, chunking, and ingestion."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.modules.knowledge_base.client import get_mongodb
from app.modules.knowledge_base.access import (
    UserAccessContext,
    can_manage,
    can_read,
    default_access,
    default_meta,
    list_filter,
    parse_access,
    parse_ingest_config,
    parse_meta,
    validate_access_for_user,
)
from app.modules.knowledge_base.chunking import chunk_pages, extract_pdf_pages
from app.modules.knowledge_base.embeddings import EMBEDDING_MODELS, embed_texts
from app.modules.knowledge_base.schema import (
    AccessVisibilityOption,
    ChunkingStrategyId,
    ChunkingStrategyOption,
    ChunkPreview,
    DocumentAccessControl,
    DocumentDetailResponse,
    DocumentMetadata,
    DocumentSettingsRequest,
    DocumentStatus,
    DocumentSummary,
    DocumentUploadResponse,
    EmbeddingModelId,
    GroupOption,
    IngestDocumentResponse,
    KnowledgeBaseOptionsResponse,
    PagePreview,
    PreviewChunksResponse,
    RoleOption,
)

logger = logging.getLogger(__name__)

CHUNKING_STRATEGIES: list[ChunkingStrategyOption] = [
    ChunkingStrategyOption(
        id="recursive",
        label="Recursive",
        description="Splits on paragraphs, sentences, then words — best default for most PDFs.",
        default_chunk_size=1000,
        default_chunk_overlap=200,
    ),
    ChunkingStrategyOption(
        id="fixed_size",
        label="Fixed size",
        description="Uniform character windows with overlap — predictable chunk lengths.",
        default_chunk_size=1000,
        default_chunk_overlap=200,
    ),
    ChunkingStrategyOption(
        id="by_page",
        label="By page",
        description="One chunk per PDF page — good when pages map to logical sections.",
        supports_chunk_size=False,
        supports_chunk_overlap=False,
        default_chunk_size=0,
        default_chunk_overlap=0,
    ),
]

ACCESS_VISIBILITY_OPTIONS: list[AccessVisibilityOption] = [
    AccessVisibilityOption(
        id="private",
        label="Private",
        description="Only you can view and manage this document.",
    ),
    AccessVisibilityOption(
        id="organization",
        label="Organization",
        description="Any signed-in user can view this document.",
    ),
    AccessVisibilityOption(
        id="group",
        label="Groups",
        description="Members of selected groups can view this document.",
    ),
    AccessVisibilityOption(
        id="role",
        label="Roles",
        description="Users with selected platform roles can view this document.",
    ),
]

ROLE_OPTIONS: list[RoleOption] = [
    RoleOption(id="OWNER", label="Owner"),
    RoleOption(id="ADMIN", label="Admin"),
    RoleOption(id="MEMBER", label="Member"),
]

ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
PREVIEW_CHUNK_LIMIT = 12


class KnowledgeBaseService:
    def options(self, groups: list[GroupOption] | None = None) -> KnowledgeBaseOptionsResponse:
        return KnowledgeBaseOptionsResponse(
            chunking_strategies=CHUNKING_STRATEGIES,
            embedding_models=EMBEDDING_MODELS,
            access_visibility_options=ACCESS_VISIBILITY_OPTIONS,
            role_options=ROLE_OPTIONS,
            groups=groups or [],
        )

    def _upload_root(self) -> Path:
        root = Path(settings.KNOWLEDGE_BASE_UPLOAD_DIR)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _doc_path(self, owner_id: UUID, document_id: UUID, filename: str) -> Path:
        suffix = Path(filename).suffix.lower() or ".pdf"
        return self._upload_root() / str(owner_id) / f"{document_id}{suffix}"

    async def _get_document_raw(self, document_id: UUID) -> dict[str, Any] | None:
        db = get_mongodb()
        return await db.kb_documents.find_one({"_id": str(document_id)})

    async def _get_document_for_read(
        self,
        ctx: UserAccessContext,
        document_id: UUID,
    ) -> dict[str, Any]:
        doc = await self._get_document_raw(document_id)
        if doc is None or not can_read(ctx, doc):
            raise HTTPException(status_code=404, detail="Document not found")
        return doc

    async def _get_document_for_manage(
        self,
        ctx: UserAccessContext,
        document_id: UUID,
    ) -> dict[str, Any]:
        doc = await self._get_document_raw(document_id)
        if doc is None or not can_manage(ctx, doc):
            raise HTTPException(status_code=404, detail="Document not found")
        return doc

    def _to_summary(self, ctx: UserAccessContext, doc: dict[str, Any]) -> DocumentSummary:
        meta = parse_meta(doc)
        if not meta.title.strip():
            meta = meta.model_copy(update={"title": doc["filename"]})
        return DocumentSummary(
            id=UUID(doc["_id"]),
            filename=doc["filename"],
            content_type=doc["content_type"],
            page_count=doc.get("page_count", 0),
            status=doc["status"],
            chunk_count=doc.get("chunk_count"),
            chunking_strategy=doc.get("chunking_strategy"),
            embedding_model=doc.get("embedding_model"),
            created_at=doc["created_at"],
            ingested_at=doc.get("ingested_at"),
            meta=meta,
            access=parse_access(doc),
            is_owner=can_manage(ctx, doc),
        )

    async def list_documents(self, ctx: UserAccessContext) -> list[DocumentSummary]:
        db = get_mongodb()
        cursor = db.kb_documents.find(list_filter(ctx)).sort("created_at", -1)
        return [self._to_summary(ctx, doc) async for doc in cursor]

    async def get_document(
        self,
        ctx: UserAccessContext,
        document_id: UUID,
    ) -> DocumentDetailResponse:
        doc = await self._get_document_for_read(ctx, document_id)
        pages = [PagePreview(**p) for p in doc.get("pages", [])]
        summary = self._to_summary(ctx, doc)
        return DocumentDetailResponse(
            **summary.model_dump(),
            pages=pages,
            error_message=doc.get("error_message"),
            ingest_config=parse_ingest_config(doc),
            can_manage=can_manage(ctx, doc),
        )

    def _parse_upload_settings(
        self,
        settings_json: str | None,
        filename: str,
    ) -> tuple[DocumentMetadata, DocumentAccessControl]:
        meta = DocumentMetadata(title=filename)
        access = DocumentAccessControl()
        if not settings_json or not settings_json.strip():
            return meta, access
        try:
            payload = json.loads(settings_json)
            req = DocumentSettingsRequest.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid settings JSON: {exc}") from exc
        if req.meta is not None:
            meta = req.meta
        if req.access is not None:
            access = req.access
        if not meta.title.strip():
            meta = meta.model_copy(update={"title": filename})
        return meta, access

    async def upload_document(
        self,
        ctx: UserAccessContext,
        file: UploadFile,
        *,
        settings_json: str | None = None,
    ) -> DocumentUploadResponse:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=400, detail="Only PDF uploads are supported for now.")

        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail="File exceeds 25 MB limit.")

        filename = file.filename or "document.pdf"
        meta, access = self._parse_upload_settings(settings_json, filename)
        try:
            validate_access_for_user(ctx, access)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        document_id = uuid4()
        path = self._doc_path(ctx.user_id, document_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

        try:
            pages = extract_pdf_pages(path)
        except Exception as exc:
            path.unlink(missing_ok=True)
            logger.exception("pdf_extract_failed document_id=%s", document_id)
            raise HTTPException(status_code=400, detail=f"Could not read PDF: {exc}") from exc

        if not any(p.text.strip() for p in pages):
            path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="PDF has no extractable text. Scanned/image-only PDFs are not supported yet.",
            )

        created_at = datetime.now(UTC)
        char_count = sum(len(p.text) for p in pages)
        record = {
            "_id": str(document_id),
            "owner_id": str(ctx.user_id),
            "filename": filename,
            "content_type": file.content_type,
            "file_path": str(path),
            "page_count": len(pages),
            "char_count": char_count,
            "pages": [p.model_dump() for p in pages],
            "status": "uploaded",
            "chunk_count": None,
            "chunking_strategy": None,
            "embedding_model": None,
            "created_at": created_at,
            "ingested_at": None,
            "error_message": None,
            "meta": meta.model_dump(),
            "access": access.model_dump(mode="json"),
            "ingest_config": {},
        }
        db = get_mongodb()
        await db.kb_documents.insert_one(record)

        return DocumentUploadResponse(
            id=document_id,
            filename=filename,
            content_type=file.content_type,
            page_count=len(pages),
            char_count=char_count,
            pages=pages,
            status="uploaded",
            created_at=created_at,
            meta=meta,
            access=access,
        )

    async def update_document_settings(
        self,
        ctx: UserAccessContext,
        document_id: UUID,
        body: DocumentSettingsRequest,
    ) -> DocumentDetailResponse:
        doc = await self._get_document_for_manage(ctx, document_id)
        if doc.get("status") == "ingested":
            raise HTTPException(
                status_code=400,
                detail="Cannot change metadata or access after a document is indexed.",
            )

        updates: dict[str, Any] = {}
        if body.meta is not None:
            meta = body.meta
            if not meta.title.strip():
                meta = meta.model_copy(update={"title": doc["filename"]})
            updates["meta"] = meta.model_dump()
        if body.access is not None:
            try:
                validate_access_for_user(ctx, body.access)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            updates["access"] = body.access.model_dump(mode="json")

        if updates:
            db = get_mongodb()
            await db.kb_documents.update_one({"_id": doc["_id"]}, {"$set": updates})

        return await self.get_document(ctx, document_id)

    async def get_file_path(self, ctx: UserAccessContext, document_id: UUID) -> Path:
        doc = await self._get_document_for_read(ctx, document_id)
        path = Path(doc["file_path"])
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Document file missing on disk")
        return path

    async def preview_chunks(
        self,
        ctx: UserAccessContext,
        document_id: UUID,
        *,
        chunking_strategy: ChunkingStrategyId,
        chunk_size: int,
        chunk_overlap: int,
    ) -> PreviewChunksResponse:
        doc = await self._get_document_for_read(ctx, document_id)
        if not can_manage(ctx, doc):
            raise HTTPException(status_code=403, detail="Only the document owner can preview chunks.")
        pages = [PagePreview(**p) for p in doc.get("pages", [])]
        chunks = chunk_pages(
            pages,
            chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        preview = [
            ChunkPreview(
                index=c.index,
                page=c.page,
                char_count=len(c.text),
                text=c.text[:600] + ("…" if len(c.text) > 600 else ""),
            )
            for c in chunks[:PREVIEW_CHUNK_LIMIT]
        ]
        return PreviewChunksResponse(
            strategy=chunking_strategy,
            chunk_size=chunk_size if chunking_strategy != "by_page" else None,
            chunk_overlap=chunk_overlap if chunking_strategy != "by_page" else None,
            total_chunks=len(chunks),
            preview=preview,
        )

    async def list_stored_chunks(
        self,
        ctx: UserAccessContext,
        document_id: UUID,
        *,
        limit: int = 12,
    ) -> PreviewChunksResponse:
        doc = await self._get_document_for_read(ctx, document_id)
        if doc.get("status") != "ingested":
            raise HTTPException(status_code=400, detail="Document is not indexed yet.")

        db = get_mongodb()
        doc_id = doc["_id"]
        total = doc.get("chunk_count")
        if total is None:
            total = await db.kb_chunks.count_documents({"document_id": doc_id})

        cursor = (
            db.kb_chunks.find({"document_id": doc_id}, {"text": 1, "index": 1, "page": 1, "char_count": 1})
            .sort("index", 1)
            .limit(limit)
        )
        preview = [
            ChunkPreview(
                index=chunk["index"],
                page=chunk.get("page"),
                char_count=chunk.get("char_count", len(chunk.get("text", ""))),
                text=chunk["text"][:600] + ("…" if len(chunk["text"]) > 600 else ""),
            )
            async for chunk in cursor
        ]
        ingest_config = parse_ingest_config(doc)
        strategy = doc.get("chunking_strategy") or "recursive"
        return PreviewChunksResponse(
            strategy=strategy,
            chunk_size=ingest_config.get("chunk_size"),
            chunk_overlap=ingest_config.get("chunk_overlap"),
            total_chunks=int(total),
            preview=preview,
        )

    async def ingest_document(
        self,
        ctx: UserAccessContext,
        document_id: UUID,
        *,
        chunking_strategy: ChunkingStrategyId,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model: EmbeddingModelId,
    ) -> IngestDocumentResponse:
        doc = await self._get_document_for_manage(ctx, document_id)
        pages = [PagePreview(**p) for p in doc.get("pages", [])]
        chunks = chunk_pages(
            pages,
            chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks produced from document.")

        db = get_mongodb()
        texts = [c.text for c in chunks]
        meta = parse_meta(doc)
        access = parse_access(doc)

        try:
            vectors = await embed_texts(embedding_model, texts)
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            await db.kb_documents.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "failed", "error_message": str(exc)}},
            )
            raise HTTPException(status_code=503, detail=f"Embedding failed: {exc}") from exc

        await db.kb_chunks.delete_many({"document_id": doc["_id"]})
        chunk_docs = [
            {
                "document_id": doc["_id"],
                "owner_id": doc["owner_id"],
                "index": chunk.index,
                "page": chunk.page,
                "text": chunk.text,
                "char_count": len(chunk.text),
                "embedding": vector,
                "embedding_model": embedding_model,
                "meta": meta.model_dump(),
                "access": access.model_dump(mode="json"),
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        if chunk_docs:
            await db.kb_chunks.insert_many(chunk_docs)

        ingested_at = datetime.now(UTC)
        await db.kb_documents.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "status": "ingested",
                    "chunk_count": len(chunks),
                    "chunking_strategy": chunking_strategy,
                    "embedding_model": embedding_model,
                    "ingested_at": ingested_at,
                    "error_message": None,
                    "ingest_config": {
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                    },
                },
            },
        )

        return IngestDocumentResponse(
            id=UUID(doc["_id"]),
            status="ingested",
            chunk_count=len(chunks),
            chunking_strategy=chunking_strategy,
            embedding_model=embedding_model,
            ingested_at=ingested_at,
        )


knowledge_base_service = KnowledgeBaseService()
