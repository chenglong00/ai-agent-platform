"""Auth routes: credential login (token), current user profile. OAuth providers are under /oauth."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security.dependencies import get_db
from app.modules.auth.rbac import RequireUser
from app.modules.auth.schema import TokenResponse
from app.modules.auth.service import auth_service
from app.modules.user.schema import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> UserResponse:
    """Return the currently authenticated user (from Bearer token)."""
    return current_user


@router.post("/token", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db_session: Annotated[AsyncSession, Depends(get_db)],
):
    """Authenticate with email + password; return a JWT access token.
    OAuth2 form sends 'username' — use the user's email as username."""
    access_token = await auth_service.login(
        db_session,
        form.username,
        form.password,
    )
    return TokenResponse(access_token=access_token)


# TODO: add register route
# TODO: add logout route
# TODO: add verify-email route
# TODO: add refresh token route
# TODO: add forgot password route
# TODO: add reset password route
# TODO: add resend verification email route
