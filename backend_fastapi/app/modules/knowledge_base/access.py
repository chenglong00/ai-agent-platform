"""Access control helpers for knowledge base documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.group.model import GroupMember
from app.modules.knowledge_base.schema import DocumentAccessControl, DocumentMetadata, Visibility
from app.modules.user.model import UserRole
from app.modules.user.schema import UserResponse


@dataclass(frozen=True)
class UserAccessContext:
    user_id: UUID
    role: UserRole
    group_ids: tuple[UUID, ...]


def default_meta(filename: str) -> dict[str, Any]:
    return DocumentMetadata(title=filename).model_dump()


def default_access() -> dict[str, Any]:
    return DocumentAccessControl().model_dump()


def parse_meta(doc: dict[str, Any]) -> DocumentMetadata:
    if "meta" in doc:
        return DocumentMetadata.model_validate(doc["meta"])
    raw = doc.get("metadata") or {}
    if isinstance(raw, dict) and ("title" in raw or "tags" in raw or "description" in raw):
        return DocumentMetadata.model_validate(raw)
    return DocumentMetadata(title=doc.get("filename", "Document"))


def parse_access(doc: dict[str, Any]) -> DocumentAccessControl:
    if "access" in doc:
        return DocumentAccessControl.model_validate(doc["access"])
    return DocumentAccessControl()


def parse_ingest_config(doc: dict[str, Any]) -> dict[str, Any]:
    if "ingest_config" in doc:
        return dict(doc["ingest_config"])
    raw = doc.get("metadata") or {}
    if isinstance(raw, dict) and ("chunk_size" in raw or "chunk_overlap" in raw):
        return {
            "chunk_size": raw.get("chunk_size"),
            "chunk_overlap": raw.get("chunk_overlap"),
        }
    return {}


def is_owner(ctx: UserAccessContext, doc: dict[str, Any]) -> bool:
    return doc.get("owner_id") == str(ctx.user_id)


def can_read(ctx: UserAccessContext, doc: dict[str, Any]) -> bool:
    if is_owner(ctx, doc):
        return True
    access = parse_access(doc)
    if access.visibility == "private":
        return False
    if access.visibility == "organization":
        return True
    if access.visibility == "group":
        user_groups = {str(g) for g in ctx.group_ids}
        allowed = {str(g) for g in access.allowed_group_ids}
        return bool(user_groups & allowed)
    if access.visibility == "role":
        return ctx.role.value in set(access.allowed_roles)
    return False


def can_manage(ctx: UserAccessContext, doc: dict[str, Any]) -> bool:
    return is_owner(ctx, doc)


def list_filter(ctx: UserAccessContext) -> dict[str, Any]:
    group_ids = [str(g) for g in ctx.group_ids]
    clauses: list[dict[str, Any]] = [{"owner_id": str(ctx.user_id)}]
    clauses.append({"access.visibility": "organization"})
    if group_ids:
        clauses.append({
            "access.visibility": "group",
            "access.allowed_group_ids": {"$in": group_ids},
        })
    clauses.append({
        "access.visibility": "role",
        "access.allowed_roles": ctx.role.value,
    })
    return {"$or": clauses}


async def build_user_access_context(
    session: AsyncSession,
    user: UserResponse,
) -> UserAccessContext:
    result = await session.exec(
        select(GroupMember.group_id).where(GroupMember.user_id == user.id),
    )
    group_ids = tuple(result.all())
    return UserAccessContext(user_id=user.id, role=user.role, group_ids=group_ids)


def validate_access_for_user(
    ctx: UserAccessContext,
    access: DocumentAccessControl,
) -> None:
    if access.visibility == "group":
        if not access.allowed_group_ids:
            raise ValueError("Select at least one group for group visibility.")
        user_groups = {str(g) for g in ctx.group_ids}
        for group_id in access.allowed_group_ids:
            if str(group_id) not in user_groups:
                raise ValueError("You can only share with groups you belong to.")
    if access.visibility == "role" and not access.allowed_roles:
        raise ValueError("Select at least one role for role-based visibility.")
