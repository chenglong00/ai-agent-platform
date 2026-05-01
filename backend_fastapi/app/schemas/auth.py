"""Auth request/response schemas."""

from pydantic import BaseModel, EmailStr, SecretStr


class LoginRequest(BaseModel):
    username: EmailStr
    password: SecretStr  # use .get_secret_value() when passing to service; not shown in logs/repr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
