"""HttpOnly cookie helpers for access and refresh tokens."""

from __future__ import annotations

from fastapi import Response
from starlette.requests import Request

from app.core.config import settings

COOKIE_ACCESS_TOKEN = "access_token"
COOKIE_REFRESH_TOKEN = "refresh_token"
REFRESH_COOKIE_PATH = f"{settings.API_V1_STR}/auth"


def _cookie_kwargs(*, max_age: int) -> dict:
    return {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "max_age": max_age,
    }


def set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    """Attach access (site-wide) and refresh (auth routes only) cookies."""
    access_max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    response.set_cookie(
        key=COOKIE_ACCESS_TOKEN,
        value=access_token,
        path="/",
        **_cookie_kwargs(max_age=access_max_age),
    )
    response.set_cookie(
        key=COOKIE_REFRESH_TOKEN,
        value=refresh_token,
        path=REFRESH_COOKIE_PATH,
        **_cookie_kwargs(max_age=refresh_max_age),
    )


def clear_auth_cookies(response: Response) -> None:
    """Remove auth cookies (logout)."""
    response.delete_cookie(key=COOKIE_ACCESS_TOKEN, path="/")
    response.delete_cookie(key=COOKIE_REFRESH_TOKEN, path=REFRESH_COOKIE_PATH)


def get_access_token_from_request(request: Request) -> str | None:
    value = request.cookies.get(COOKIE_ACCESS_TOKEN)
    return value.strip() if value else None


def get_refresh_token_from_request(request: Request) -> str | None:
    value = request.cookies.get(COOKIE_REFRESH_TOKEN)
    return value.strip() if value else None
