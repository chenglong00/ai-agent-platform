"""Persist and refresh OAuth tokens for enterprise connectors."""

from __future__ import annotations

import base64
import json
import logging
from datetime import timedelta
from uuid import UUID

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security.oauth import is_google_oauth_configured
from app.modules.connector.model import UserConnector
from app.utils.datetime import now_utc

logger = logging.getLogger(__name__)

_TOKEN_REFRESH_SKEW = timedelta(minutes=2)
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def extract_google_account_email(token_payload: dict) -> str | None:
    """Best-effort email from OAuth token response (id_token or userinfo)."""
    email = _email_from_id_token(token_payload.get("id_token"))
    if email:
        return email
    return None


def _email_from_id_token(id_token: str | None) -> str | None:
    if not id_token or not isinstance(id_token, str):
        return None
    parts = id_token.split(".")
    if len(parts) < 2:
        return None
    try:
        padding = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
    except (json.JSONDecodeError, ValueError):
        return None
    email = payload.get("email")
    return str(email) if email else None


class ConnectorAuthManager:
    async def upsert_tokens(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        connector_id: str,
        access_token: str,
        refresh_token: str | None,
        expires_in: int | None,
        scopes: str | None,
        account_email: str | None = None,
    ) -> UserConnector:
        row = await self._get_row(session, user_id, connector_id)
        expires_at = None
        if expires_in is not None:
            expires_at = now_utc() + timedelta(seconds=int(expires_in))

        if row is None:
            row = UserConnector(
                user_id=user_id,
                connector_id=connector_id,
                enabled=True,
            )
            session.add(row)

        row.access_token = access_token
        if refresh_token:
            row.refresh_token = refresh_token
        row.token_expires_at = expires_at
        row.scopes = scopes
        row.account_email = account_email
        row.last_connected_at = now_utc()
        row.last_error = None
        row.updated_at = now_utc()
        await session.commit()
        await session.refresh(row)
        return row

    async def disconnect(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        connector_id: str,
    ) -> None:
        row = await self._get_row(session, user_id, connector_id)
        if row is None:
            return
        await session.delete(row)
        await session.commit()

    async def set_enabled(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        connector_id: str,
        enabled: bool,
    ) -> UserConnector:
        row = await self._require_row(session, user_id, connector_id)
        row.enabled = enabled
        row.updated_at = now_utc()
        await session.commit()
        await session.refresh(row)
        return row

    async def get_valid_access_token(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        connector_id: str,
    ) -> str:
        row = await self._require_row(session, user_id, connector_id)
        if not row.access_token:
            raise ValueError("Connector is not authenticated")

        if row.token_expires_at is None:
            return row.access_token

        if row.token_expires_at > now_utc() + _TOKEN_REFRESH_SKEW:
            return row.access_token

        if not row.refresh_token:
            raise ValueError("Access token expired and no refresh token is stored")

        refreshed = await self._refresh_google_token(row.refresh_token)
        row.access_token = refreshed["access_token"]
        expires_in = refreshed.get("expires_in")
        if expires_in is not None:
            row.token_expires_at = now_utc() + timedelta(seconds=int(expires_in))
        if refreshed.get("refresh_token"):
            row.refresh_token = refreshed["refresh_token"]
        row.updated_at = now_utc()
        row.last_error = None
        await session.commit()
        return row.access_token

    async def fetch_google_account_email(
        self,
        access_token: str,
        *,
        token_payload: dict | None = None,
    ) -> str | None:
        if token_payload:
            email = extract_google_account_email(token_payload)
            if email:
                return email

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    _GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code == 401:
                    logger.debug("connector_userinfo_unauthorized (missing openid/email scope)")
                    return None
                resp.raise_for_status()
                payload = resp.json()
                return payload.get("email")
        except httpx.HTTPStatusError as exc:
            logger.debug("connector_userinfo_failed status=%s", exc.response.status_code)
            return None
        except Exception:
            logger.warning("connector_userinfo_failed", exc_info=True)
            return None

    async def _refresh_google_token(self, refresh_token: str) -> dict:
        if not is_google_oauth_configured():
            raise ValueError("Google OAuth is not configured")

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if resp.status_code >= 400:
                raise ValueError(f"Token refresh failed: {resp.text[:200]}")
            return resp.json()

    async def _get_row(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: str,
    ) -> UserConnector | None:
        statement = select(UserConnector).where(
            UserConnector.user_id == user_id,
            UserConnector.connector_id == connector_id,
        )
        return (await session.exec(statement)).first()

    async def _require_row(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: str,
    ) -> UserConnector:
        row = await self._get_row(session, user_id, connector_id)
        if row is None:
            raise ValueError("Connector is not connected")
        return row


connector_auth_manager = ConnectorAuthManager()
