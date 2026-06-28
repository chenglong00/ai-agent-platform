"""Auth business logic: credential verification and token creation.

Service uses plain types (str in/out); no API request/response models.
The API layer is responsible for Pydantic models and HTTP status codes.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security.password import PASSWORD_ALGO, hash_password, verify_password
from app.modules.auth.model import AuthIdentity, AuthProvider
from app.modules.user.model import User
from app.utils.validation import normalize_email, normalize_password


class AuthService:
    """Stateless auth logic. Pass session per call so one instance can serve all requests."""

    async def login(self, session: AsyncSession, email: str, password: str) -> str:
        """Verify email/password and return a JWT access token string."""
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

        return self._create_access_token(user.id)

    async def register(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> str:
        """Create a new user with email/password identity. Returns access token. Raises ConflictError if email exists."""
        email = normalize_email(email)
        password = normalize_password(password)

        if await self.get_user_by_email(session, email) is not None:
            raise ConflictError("An account with this email already exists.")

        user = User(email=email, display_name=display_name or None)
        session.add(user)
        await session.flush()  # get user.id

        identity = AuthIdentity(
            user_id=user.id,
            provider=AuthProvider.credentials,
            password_hash=hash_password(password),
            password_algo=PASSWORD_ALGO,
        )
        session.add(identity)
        await session.commit()
        await session.refresh(user)

        return self._create_access_token(user.id)

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
    ) -> str:
        """Find or create user and OAuth identity; return JWT. Email must be normalized (lowercase). Use for Google, GitHub, Microsoft, etc."""
        if provider == AuthProvider.credentials:
            raise ValueError("Use login_for_access_token or register for credentials")

        # Existing OAuth identity
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
            await session.commit()
            return self._create_access_token(user.id)

        # Existing user by email: link OAuth identity
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
            await session.commit()
            await session.refresh(user)
            return self._create_access_token(user.id)

        # New user
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
        await session.commit()
        await session.refresh(user)
        return self._create_access_token(user.id)

    def _create_access_token(self, user_id: UUID) -> str:
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),  # subject: who the token is for (standard claim)
            "exp": exp,  # expiration (required)
            "iat": now,  # issued at (optional, useful for auditing)
        }
        return jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )


# Single instance; pass session per request in each method call.
auth_service = AuthService()