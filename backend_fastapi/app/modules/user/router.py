"""Admin user management routes (require OWNER or ADMIN)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security.dependencies import get_db
from app.modules.auth.rbac import RequireAdmin
from app.modules.user.model import UserRole
from app.modules.user.schema import AdminCreateUserRequest, AdminUpdateUserRequest, UserResponse
from app.modules.user.service import user_service

users_router = APIRouter()


@users_router.get("/")
async def list_users(
    session: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List users with pagination."""
    users, total = await user_service.list_users(session, skip=skip, limit=limit)
    return {"items": [UserResponse.model_validate(u) for u in users], "total": total}


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a user by id."""
    user = await user_service.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@users_router.post("/", status_code=201, response_model=UserResponse)
async def create_user(
    body: AdminCreateUserRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create a new user with email/password. Cannot set role to OWNER."""
    if body.role == UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot create owner via this endpoint")
    user = await user_service.create_user(
        session,
        body.email,
        body.password.get_secret_value(),
        body.display_name,
        body.role,
        body.is_approved,
    )
    return UserResponse.model_validate(user)


@users_router.patch("/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Set is_approved=True for the given user."""
    user = await user_service.approve_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@users_router.patch("/{user_id}/reject", response_model=UserResponse)
async def reject_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Set is_approved=False for the given user."""
    user = await user_service.reject_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@users_router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: AdminUpdateUserRequest,
    session: AsyncSession = Depends(get_db),
):
    """Update user by id. Only provided fields are updated. Cannot set role to OWNER."""
    if body.role == UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot set role to owner via this endpoint")
    user = await user_service.update_user(
        session,
        user_id,
        email=body.email,
        display_name=body.display_name,
        avatar_url=body.avatar_url,
        role=body.role,
        is_approved=body.is_approved,
        is_active=body.is_active,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@users_router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Delete user and their auth identities."""
    deleted = await user_service.delete_user(session, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")


router = APIRouter(
    dependencies=[Depends(RequireAdmin)],
    tags=["admin"],
)
router.include_router(users_router, prefix="/users")
