"""JWT authentication dependencies for protected routes."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID

from app.core.config import settings
from app.core.observability.logging import user_id_ctx
from app.core.security.dependencies import get_db
from app.modules.auth.cookies import get_access_token_from_request
from app.modules.user.model import User
from app.modules.user.schema import UserResponse

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    auto_error=False,
)


def _decode_token_payload(token: str) -> dict:
    payload = None
    for key in (settings.SECRET_KEY, settings.SECRET_KEY_PREVIOUS):
        if not key:
            continue
        try:
            payload = jwt.decode(token, key, algorithms=[settings.ALGORITHM])
            break
        except jwt.InvalidTokenError:
            continue
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


async def get_user_from_token(session: AsyncSession, token: str) -> UserResponse:
    """Validate a Bearer JWT string and return the active user."""
    payload = _decode_token_payload(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        user_id = UUID(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id_ctx.set(str(user.id))
    return UserResponse.model_validate(user)


def _resolve_access_token(request: Request, bearer_token: str | None) -> str:
    token = bearer_token or get_access_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


async def get_access_token_string(
    request: Request,
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> str:
    """Return raw access JWT from Authorization header or cookie."""
    return _resolve_access_token(request, bearer_token)


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> UserResponse:
    """Validate JWT from Authorization header or access_token cookie."""
    token = _resolve_access_token(request, bearer_token)
    return await get_user_from_token(session, token)
