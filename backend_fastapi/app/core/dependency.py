"""FastAPI dependency providers for route injection (e.g. Depends(get_db))."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.config import settings
from app.modules.user.model import User, UserRole
from app.modules.user.schema import UserResponse

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async session for dependency injection. Use with Depends(get_db) in route handlers.
    Route handlers should call await session.commit() after making changes. On exception the session is rolled back;
    the session is closed when the request ends."""
    from app.core.database import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    token: str = Depends(oauth2_scheme),
) -> UserResponse:
    """Validate Bearer JWT and return the current User. Raises 401 if missing or invalid.
    Supports key rotation: verifies with SECRET_KEY first, then SECRET_KEY_PREVIOUS if set."""
    # Must match signing in auth_service._create_access_token (no min-length skip there).
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
    return UserResponse.model_validate(user)


def require_roles(*allowed: UserRole):
    def role_checker(current_user: Annotated[UserResponse, Depends(get_current_user)]) -> UserResponse:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user
    return role_checker


# Convenience dependency aliases
RequireOwner = require_roles(UserRole.OWNER)
RequireAdmin = require_roles(UserRole.OWNER, UserRole.ADMIN)
RequireUser = require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.MEMBER)
