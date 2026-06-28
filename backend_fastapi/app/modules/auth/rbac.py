"""Route-level role-based access control dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.modules.auth.dependencies import get_current_user
from app.modules.user.model import UserRole
from app.modules.user.schema import UserResponse


def require_roles(*allowed: UserRole):
    def role_checker(current_user: Annotated[UserResponse, Depends(get_current_user)]) -> UserResponse:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return role_checker


RequireOwner = require_roles(UserRole.OWNER)
RequireAdmin = require_roles(UserRole.OWNER, UserRole.ADMIN)
RequireUser = require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.MEMBER)
