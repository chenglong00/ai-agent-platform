"""JWT authentication dependencies for protected routes."""

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.observability.logging import user_id_ctx
from app.core.security.dependencies import get_db
from app.modules.user.model import User
from app.modules.user.schema import UserResponse

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")


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


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    token: str = Depends(oauth2_scheme),
) -> UserResponse:
    """Validate Bearer JWT and return the current User. Raises 401 if missing or invalid.
    Supports key rotation: verifies with SECRET_KEY first, then SECRET_KEY_PREVIOUS if set."""
    return await get_user_from_token(session, token)
