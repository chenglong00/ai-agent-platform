"""Signed OAuth state and Google token exchange for connectors."""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer

from app.core.config import settings
from app.core.security.oauth import is_google_oauth_configured

logger = logging.getLogger(__name__)

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_STATE_MAX_AGE_SECONDS = 600


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt="connector-oauth-state")


def sign_oauth_state(*, user_id: str, connector_id: str) -> str:
    return _serializer().dumps({"user_id": user_id, "connector_id": connector_id})


def verify_oauth_state(state: str) -> tuple[str, str]:
    try:
        payload = _serializer().loads(state, max_age=_STATE_MAX_AGE_SECONDS)
    except (BadSignature, BadTimeSignature) as exc:
        raise ValueError("Invalid or expired OAuth state") from exc
    user_id = payload.get("user_id")
    connector_id = payload.get("connector_id")
    if not user_id or not connector_id:
        raise ValueError("OAuth state is missing required fields")
    return str(user_id), str(connector_id)


def build_google_authorize_url(*, connector_id: str, scopes: tuple[str, ...], state: str) -> str:
    if not is_google_oauth_configured():
        raise ValueError("Google OAuth is not configured")
    redirect_uri = settings.CONNECTOR_OAUTH_REDIRECT_URI.strip()
    if not redirect_uri:
        raise ValueError("CONNECTOR_OAUTH_REDIRECT_URI is not configured")

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_google_code(code: str) -> dict:
    if not is_google_oauth_configured():
        raise ValueError("Google OAuth is not configured")
    redirect_uri = settings.CONNECTOR_OAUTH_REDIRECT_URI.strip()
    if not redirect_uri:
        raise ValueError("CONNECTOR_OAUTH_REDIRECT_URI is not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code >= 400:
            logger.warning("connector_oauth_exchange_failed status=%s body=%s", resp.status_code, resp.text[:300])
            raise ValueError("Failed to exchange authorization code")
        return resp.json()


def build_connector_success_redirect(*, connector_id: str, status: str = "connected") -> str:
    base = settings.CONNECTOR_SUCCESS_REDIRECT_URL.strip() or "http://localhost:3000/connector"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}status={status}&connector={connector_id}"
