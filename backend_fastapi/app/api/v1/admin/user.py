"""Admin user management: list, get, create, approve, reject."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.dependency import get_db
from app.core.exceptions import ConflictError
from app.models.user import UserRole
from app.schemas.user import AdminCreateUserRequest, AdminUpdateUserRequest, UserResponse
from app.services.admin_user_service import admin_user_service

router = APIRouter()


@router.get("/")
async def list_users(
    session: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List users with pagination."""
    users, total = await admin_user_service.list_users(session, skip=skip, limit=limit)
    return {"items": [UserResponse.model_validate(u) for u in users], "total": total}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a user by id."""
    user = await admin_user_service.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.post("/", status_code=201, response_model=UserResponse)
async def create_user(
    body: AdminCreateUserRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create a new user with email/password. Cannot set role to OWNER."""
    if body.role == UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot create owner via this endpoint")
    try:
        user = await admin_user_service.create_user(
            session,
            body.email,
            body.password.get_secret_value(),
            body.display_name,
            body.role,
            body.is_approved,
        )
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=e.message)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Set is_approved=True for the given user."""
    user = await admin_user_service.approve_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/reject", response_model=UserResponse)
async def reject_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Set is_approved=False for the given user."""
    user = await admin_user_service.reject_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: AdminUpdateUserRequest,
    session: AsyncSession = Depends(get_db),
):
    """Update user by id. Only provided fields are updated. Cannot set role to OWNER."""
    if body.role == UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot set role to owner via this endpoint")
    try:
        user = await admin_user_service.update_user(
            session,
            user_id,
            email=body.email,
            display_name=body.display_name,
            avatar_url=body.avatar_url,
            role=body.role,
            is_approved=body.is_approved,
            is_active=body.is_active,
        )
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=e.message)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Delete user and their auth identities."""
    deleted = await admin_user_service.delete_user(session, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
