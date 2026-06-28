"""Knowledge base API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ChunkingStrategyId = Literal["fixed_size", "recursive", "by_page"]
ParsingStrategyId = Literal["pypdf", "gemini"]
DocumentStatus = Literal["uploaded", "ingested", "failed"]
EmbeddingModelId = Literal["text-embedding-004", "text-embedding-005", "textembedding-gecko@003"]
Visibility = Literal["private", "organization", "group", "role"]


class ChunkingStrategyOption(BaseModel):
    id: ChunkingStrategyId
    label: str
    description: str
    supports_chunk_size: bool = True
    supports_chunk_overlap: bool = True
    default_chunk_size: int = 1000
    default_chunk_overlap: int = 200


class ParsingStrategyOption(BaseModel):
    id: ParsingStrategyId
    label: str
    description: str


class EmbeddingModelOption(BaseModel):
    id: EmbeddingModelId
    label: str
    description: str
    dimensions: int


class AccessVisibilityOption(BaseModel):
    id: Visibility
    label: str
    description: str


class GroupOption(BaseModel):
    id: UUID
    name: str


class RoleOption(BaseModel):
    id: str
    label: str


class DocumentMetadata(BaseModel):
    title: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list)
    custom: dict[str, str] = Field(default_factory=dict)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [t.strip() for t in value.split(",") if t.strip()]
        return value


class DocumentAccessControl(BaseModel):
    visibility: Visibility = "private"
    allowed_group_ids: list[UUID] = Field(default_factory=list)
    allowed_roles: list[str] = Field(default_factory=list)


class DocumentSettingsRequest(BaseModel):
    meta: DocumentMetadata | None = None
    access: DocumentAccessControl | None = None


class KnowledgeBaseOptionsResponse(BaseModel):
    parsing_strategies: list[ParsingStrategyOption]
    chunking_strategies: list[ChunkingStrategyOption]
    embedding_models: list[EmbeddingModelOption]
    access_visibility_options: list[AccessVisibilityOption]
    role_options: list[RoleOption]
    groups: list[GroupOption] = Field(default_factory=list)


class PagePreview(BaseModel):
    page: int
    text: str


class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    page_count: int
    char_count: int
    pages: list[PagePreview]
    status: DocumentStatus
    parsing_strategy: ParsingStrategyId
    created_at: datetime
    meta: DocumentMetadata
    access: DocumentAccessControl


class DocumentSummary(BaseModel):
    id: UUID
    filename: str
    content_type: str
    page_count: int
    status: DocumentStatus
    parsing_strategy: ParsingStrategyId | None = None
    chunk_count: int | None = None
    chunking_strategy: ChunkingStrategyId | None = None
    embedding_model: EmbeddingModelId | None = None
    created_at: datetime
    ingested_at: datetime | None = None
    meta: DocumentMetadata
    access: DocumentAccessControl
    is_owner: bool = False


class PreviewChunksRequest(BaseModel):
    chunking_strategy: ChunkingStrategyId = "recursive"
    chunk_size: int = Field(default=1000, ge=200, le=8000)
    chunk_overlap: int = Field(default=200, ge=0, le=2000)


class ChunkPreview(BaseModel):
    index: int
    page: int | None = None
    char_count: int
    text: str


class PreviewChunksResponse(BaseModel):
    strategy: ChunkingStrategyId
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    total_chunks: int
    preview: list[ChunkPreview]


class IngestDocumentRequest(PreviewChunksRequest):
    embedding_model: EmbeddingModelId = "text-embedding-004"


class IngestDocumentResponse(BaseModel):
    id: UUID
    status: DocumentStatus
    chunk_count: int
    chunking_strategy: ChunkingStrategyId
    embedding_model: EmbeddingModelId
    ingested_at: datetime


class DeleteDocumentResponse(BaseModel):
    id: UUID
    deleted: bool = True


class DocumentDetailResponse(DocumentSummary):
    pages: list[PagePreview] = Field(default_factory=list)
    error_message: str | None = None
    ingest_config: dict[str, Any] = Field(default_factory=dict)
    can_manage: bool = False
