"""Admin/owner-only routes. All endpoints require OWNER or ADMIN role."""

from fastapi import APIRouter, Depends

from app.api.v1.admin.user import router as user_router
from app.core.dependency import RequireAdmin

router = APIRouter(
    dependencies=[Depends(RequireAdmin)],
    tags=["admin"],
)

router.include_router(user_router, prefix="/users")
