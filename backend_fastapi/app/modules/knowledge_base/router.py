"""Knowledge base API: upload, preview, chunk, and ingest documents."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security.dependencies import get_db
from app.modules.auth.rbac import RequireUser
from app.modules.knowledge_base.client import get_mongodb
from app.modules.group.model import GroupMember, UserGroup
from app.modules.knowledge_base.access import UserAccessContext
from app.modules.knowledge_base.schema import (
    DocumentDetailResponse,
    DocumentSettingsRequest,
    DocumentSummary,
    DocumentUploadResponse,
    GroupOption,
    IngestDocumentRequest,
    IngestDocumentResponse,
    KnowledgeBaseOptionsResponse,
    PreviewChunksRequest,
    PreviewChunksResponse,
)
from app.modules.knowledge_base.service import knowledge_base_service
from app.modules.user.schema import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_mongodb() -> None:
    try:
        get_mongodb()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not configured. Set MONGODB_URI and start the mongodb service.",
        ) from exc


async def _access_context(
    session: AsyncSession,
    user: UserResponse,
) -> UserAccessContext:
    result = await session.exec(
        select(GroupMember.group_id).where(GroupMember.user_id == user.id),
    )
    group_ids = tuple(result.all())
    return UserAccessContext(user_id=user.id, role=user.role, group_ids=group_ids)


async def _user_groups(session: AsyncSession, user: UserResponse) -> list[GroupOption]:
    statement = (
        select(UserGroup)
        .join(GroupMember, GroupMember.group_id == UserGroup.id)
        .where(GroupMember.user_id == user.id)
        .order_by(UserGroup.name.asc())
    )
    result = await session.exec(statement)
    return [GroupOption(id=g.id, name=g.name) for g in result.all()]


@router.get("/options", response_model=KnowledgeBaseOptionsResponse)
async def get_options(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> KnowledgeBaseOptionsResponse:
    _require_mongodb()
    groups = await _user_groups(session, current_user)
    return knowledge_base_service.options(groups=groups)


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> list[DocumentSummary]:
    _require_mongodb()
    ctx = await _access_context(session, current_user)
    return await knowledge_base_service.list_documents(ctx)


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> DocumentDetailResponse:
    _require_mongodb()
    ctx = await _access_context(session, current_user)
    return await knowledge_base_service.get_document(ctx, document_id)


@router.patch("/documents/{document_id}", response_model=DocumentDetailResponse)
async def update_document_settings(
    document_id: UUID,
    body: DocumentSettingsRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> DocumentDetailResponse:
    _require_mongodb()
    ctx = await _access_context(session, current_user)
    return await knowledge_base_service.update_document_settings(ctx, document_id, body)


@router.get("/documents/{document_id}/file")
async def get_document_file(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> FileResponse:
    _require_mongodb()
    ctx = await _access_context(session, current_user)
    doc = await knowledge_base_service.get_document(ctx, document_id)
    path = await knowledge_base_service.get_file_path(ctx, document_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=doc.filename,
    )


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
    file: Annotated[UploadFile, File(description="PDF document to ingest")],
    settings: Annotated[str | None, Form(description="JSON DocumentSettingsRequest")] = None,
) -> DocumentUploadResponse:
    _require_mongodb()
    ctx = await _access_context(session, current_user)
    return await knowledge_base_service.upload_document(
        ctx,
        file,
        settings_json=settings,
    )


@router.post(
    "/documents/{document_id}/preview-chunks",
    response_model=PreviewChunksResponse,
)
async def preview_chunks(
    document_id: UUID,
    body: PreviewChunksRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> PreviewChunksResponse:
    _require_mongodb()
    ctx = await _access_context(session, current_user)
    return await knowledge_base_service.preview_chunks(
        ctx,
        document_id,
        chunking_strategy=body.chunking_strategy,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
    )


@router.post(
    "/documents/{document_id}/ingest",
    response_model=IngestDocumentResponse,
)
async def ingest_document(
    document_id: UUID,
    body: IngestDocumentRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> IngestDocumentResponse:
    _require_mongodb()
    ctx = await _access_context(session, current_user)
    return await knowledge_base_service.ingest_document(
        ctx,
        document_id,
        chunking_strategy=body.chunking_strategy,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        embedding_model=body.embedding_model,
    )


@router.get(
    "/documents/{document_id}/chunks",
    response_model=PreviewChunksResponse,
)
async def list_document_chunks(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
    limit: Annotated[int, Query(ge=1, le=100)] = 12,
) -> PreviewChunksResponse:
    _require_mongodb()
    ctx = await _access_context(session, current_user)
    return await knowledge_base_service.list_stored_chunks(
        ctx,
        document_id,
        limit=limit,
    )
