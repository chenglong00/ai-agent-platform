"""User-related request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, SecretStr

from app.modules.user.model import UserRole


class UserResponse(BaseModel):
    """User payload for API responses (list, get, create, update, approve, reject)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: Optional[str] = None
    role: UserRole
    is_approved: bool
    is_active: bool
    created_at: Optional[datetime] = None


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: SecretStr
    display_name: str | None = None
    role: UserRole = UserRole.MEMBER
    is_approved: bool = False


class AdminUpdateUserRequest(BaseModel):
    """All fields optional for PATCH."""

    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[UserRole] = None
    is_approved: Optional[bool] = None
    is_active: Optional[bool] = None
