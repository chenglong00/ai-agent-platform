"""Auth routes: credential login (token). OAuth providers are under /oauth."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.dependency import get_db
from app.core.exceptions import AuthenticationError
from app.modules.auth.me_router import router as me_router
from app.modules.auth.schema import TokenResponse
from app.modules.auth.service import auth_service

router = APIRouter()

router.include_router(me_router)


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


# TODO: add register route
# TODO: add logout route
# TODO: add verify-email route
# TODO: add refresh token route
# TODO: add forgot password route
# TODO: add reset password route
# TODO: add resend verification email route