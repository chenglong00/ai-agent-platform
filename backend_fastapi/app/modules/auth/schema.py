"""Auth request/response schemas."""

from pydantic import BaseModel, EmailStr, Field, SecretStr


class LoginRequest(BaseModel):
    username: EmailStr
    password: SecretStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=8)
    display_name: str | None = Field(default=None, max_length=255)


class TokenResponse(BaseModel):
    """Tokens are delivered via httpOnly cookies; body confirms success only."""

    token_type: str = "bearer"
    message: str = "Authenticated"


class WsTokenResponse(BaseModel):
    """Short-lived access token for WebSocket connections (cookie auth required)."""

    access_token: str
    token_type: str = "bearer"
