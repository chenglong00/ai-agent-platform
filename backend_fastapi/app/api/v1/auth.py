"""Auth routes: credential login (token). OAuth providers are under /oauth."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Annotated

from app.core.dependency import RequireUser, get_db
from app.core.exceptions import AuthenticationError
from app.schemas.auth import TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import auth_service

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db_session: Annotated[AsyncSession, Depends(get_db)],
):
    """Authenticate with email + password; return a JWT access token.
    OAuth2 form sends 'username' — use the user's email as username."""
    try:
        access_token = await auth_service.login(
            db_session,
            form.username,
            form.password,
        )
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> UserResponse:
    """Return the currently authenticated user (from Bearer token)."""
    return current_user


# TODO: add register route
# TODO: add logout route
# TODO: add verify-email route
# TODO: add refresh token route
# TODO: add forgot password route
# TODO: add reset password route
# TODO: add resend verification email route