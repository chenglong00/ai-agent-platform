"""Auth business logic: credential verification and token creation.

Service uses plain types (str in/out); no API request/response models.
The API layer is responsible for Pydantic models and HTTP status codes.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security.password import PASSWORD_ALGO, hash_password, verify_password
from app.modules.auth.model import AuthIdentity, AuthProvider
from app.modules.auth.refresh_token_model import RefreshToken
from app.modules.user.model import User
from app.utils.validation import normalize_email, normalize_password


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class AuthService:
    """Stateless auth logic. Pass session per call so one instance can serve all requests."""

    async def login(self, session: AsyncSession, email: str, password: str) -> TokenPair:
        """Verify email/password and return access + refresh tokens."""
        email = normalize_email(email)
        password = normalize_password(password)

        user = await self.get_user_by_email(session, email)
        if not user or not user.is_active:
            raise AuthenticationError()

        result = await session.execute(
            select(AuthIdentity).where(
                AuthIdentity.user_id == user.id,
                AuthIdentity.provider == AuthProvider.credentials,
            )
        )
        identity = result.scalars().first()
        if not identity or not identity.password_hash:
            raise AuthenticationError()

        if not verify_password(password, identity.password_hash):
            raise AuthenticationError()

        return await self._issue_session(session, user.id)

    async def register(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> TokenPair:
        """Create a new user with email/password identity. Raises ConflictError if email exists."""
        email = normalize_email(email)
        password = normalize_password(password)

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        if await self.get_user_by_email(session, email) is not None:
            raise ConflictError("An account with this email already exists.")

        user = User(email=email, display_name=display_name or None)
        session.add(user)
        await session.flush()

        identity = AuthIdentity(
            user_id=user.id,
            provider=AuthProvider.credentials,
            password_hash=hash_password(password),
            password_algo=PASSWORD_ALGO,
        )
        session.add(identity)
        await session.flush()
        return await self._issue_session(session, user.id)

    async def refresh_session(
        self,
        session: AsyncSession,
        refresh_token: str,
    ) -> TokenPair:
        """Validate refresh token, rotate it, and return a new token pair."""
        token_hash = self._hash_refresh_token(refresh_token)
        now = datetime.now(UTC)
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
        stored = result.scalars().first()
        if not stored:
            raise AuthenticationError("Invalid or expired refresh token")

        user = await session.get(User, stored.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("Invalid or expired refresh token")

        stored.revoked_at = now
        session.add(stored)
        await session.flush()
        return await self._issue_session(session, user.id)

    async def revoke_refresh_token(self, session: AsyncSession, refresh_token: str) -> None:
        """Revoke a refresh token (logout). No-op if token is unknown."""
        token_hash = self._hash_refresh_token(refresh_token)
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
        )
        stored = result.scalars().first()
        if not stored:
            return
        stored.revoked_at = datetime.now(UTC)
        session.add(stored)
        await session.commit()

    async def get_user_by_email(self, session: AsyncSession, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await session.execute(statement)
        return result.scalars().first()

    async def login_or_register_oauth(
        self,
        session: AsyncSession,
        *,
        provider: AuthProvider,
        provider_user_id: str,
        email: str,
        name: str | None = None,
        picture: str | None = None,
    ) -> TokenPair:
        """Find or create user and OAuth identity; return token pair."""
        if provider == AuthProvider.credentials:
            raise ValueError("Use login or register for credentials")

        result = await session.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == provider,
                AuthIdentity.provider_user_id == provider_user_id,
            )
        )
        identity = result.scalars().first()
        if identity:
            user = await session.get(User, identity.user_id)
            if not user or not user.is_active:
                raise AuthenticationError(
                    "Account is disabled or not allowed",
                    status_code=403,
                )
            identity.last_login_at = datetime.now(UTC)
            if name is not None:
                user.display_name = name
            if picture is not None:
                user.avatar_url = picture
            user.updated_at = datetime.now(UTC)
            session.add(identity)
            session.add(user)
            await session.flush()
            return await self._issue_session(session, user.id)

        user = await self.get_user_by_email(session, email)
        if user:
            if not user.is_active:
                raise AuthenticationError(
                    "Account is disabled or not allowed",
                    status_code=403,
                )
            identity = AuthIdentity(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                email_verified=True,
                last_login_at=datetime.now(UTC),
            )
            session.add(identity)
            if name is not None:
                user.display_name = user.display_name or name
            if picture is not None:
                user.avatar_url = picture
            user.updated_at = datetime.now(UTC)
            session.add(user)
            await session.flush()
            return await self._issue_session(session, user.id)

        user = User(
            email=email,
            display_name=name or None,
            avatar_url=picture or None,
            is_approved=True,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        identity = AuthIdentity(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email_verified=True,
            last_login_at=datetime.now(UTC),
        )
        session.add(identity)
        await session.flush()
        return await self._issue_session(session, user.id)

    async def _issue_session(self, session: AsyncSession, user_id: UUID) -> TokenPair:
        access_token = self._create_access_token(user_id)
        refresh_raw = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session.add(
            RefreshToken(
                user_id=user_id,
                token_hash=self._hash_refresh_token(refresh_raw),
                expires_at=expires_at,
            )
        )
        await session.commit()
        return TokenPair(access_token=access_token, refresh_token=refresh_raw)

    def _create_access_token(self, user_id: UUID) -> str:
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "exp": exp,
            "iat": now,
        }
        return jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


auth_service = AuthService()
