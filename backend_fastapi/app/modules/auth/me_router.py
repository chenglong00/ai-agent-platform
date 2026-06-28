"""Current user profile (GET /me)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependency import RequireUser
from app.modules.user.schema import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> UserResponse:
    """Return the currently authenticated user (from Bearer token)."""
    return current_user
