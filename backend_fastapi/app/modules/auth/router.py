"""Auth routes: credential login, register, refresh, logout, current user profile."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.http.limiter import limiter
from app.core.security.dependencies import get_db
from app.modules.auth.cookies import (
    clear_auth_cookies,
    get_refresh_token_from_request,
    set_auth_cookies,
)
from app.modules.auth.dependencies import get_access_token_string, get_current_user
from app.modules.auth.rbac import RequireUser
from app.modules.auth.schema import RegisterRequest, TokenResponse, WsTokenResponse
from app.modules.auth.service import auth_service
from app.modules.user.schema import UserResponse

router = APIRouter()


def _apply_session_cookies(response: Response, tokens) -> None:
    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> UserResponse:
    """Return the currently authenticated user."""
    return current_user


@router.get("/ws-token", response_model=WsTokenResponse)
async def get_ws_token(
    token: Annotated[str, Depends(get_access_token_string)],
    _current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> WsTokenResponse:
    """Return the access JWT for WebSocket auth (requires valid session cookie)."""
    return WsTokenResponse(access_token=token)


@router.post("/token", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db_session: Annotated[AsyncSession, Depends(get_db)],
):
    """Authenticate with email + password; sets httpOnly auth cookies."""
    tokens = await auth_service.login(
        db_session,
        form.username,
        form.password,
    )
    _apply_session_cookies(response, tokens)
    return TokenResponse()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest,
    db_session: Annotated[AsyncSession, Depends(get_db)],
):
    """Create account with email + password; sets httpOnly auth cookies."""
    try:
        tokens = await auth_service.register(
            db_session,
            body.email,
            body.password.get_secret_value(),
            display_name=body.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    _apply_session_cookies(response, tokens)
    return TokenResponse()


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    db_session: Annotated[AsyncSession, Depends(get_db)],
):
    """Rotate refresh token and issue new access token (httpOnly cookies)."""
    refresh_token = get_refresh_token_from_request(request)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    try:
        tokens = await auth_service.refresh_session(db_session, refresh_token)
    except AuthenticationError as exc:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail=exc.message) from exc
    _apply_session_cookies(response, tokens)
    return TokenResponse()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db_session: Annotated[AsyncSession, Depends(get_db)],
):
    """Revoke refresh token and clear auth cookies."""
    refresh_token = get_refresh_token_from_request(request)
    if refresh_token:
        await auth_service.revoke_refresh_token(db_session, refresh_token)
    clear_auth_cookies(response)
