"""User management for admins: list, get, create, update, delete, approve, reject."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ConflictError
from app.core.password import PASSWORD_ALGO, hash_password
from app.modules.auth.model import AuthIdentity, AuthProvider
from app.modules.user.model import User, UserRole
from app.utils.validation import normalize_email, normalize_password


class UserService:
    """Admin user management. Pass session per call."""

    async def list_users(
        self,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        """Return (users, total count). Ordered by created_at desc."""
        total_result = await session.execute(select(func.count(User.id)))
        total = total_result.scalar()
        statement = (
            select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
        )
        result = await session.execute(statement)
        users = list(result.scalars().all())
        return users, total

    async def get_user(self, session: AsyncSession, user_id: UUID) -> User | None:
        """Return user by id or None if not found."""
        return await session.get(User, user_id)

    async def create_user(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        display_name: str | None = None,
        role: UserRole = UserRole.MEMBER,
        is_approved: bool = False,
    ) -> User:
        """Create a new user with email/password identity. Raises ConflictError if email exists."""
        email = normalize_email(email)
        password = normalize_password(password)

        if await self._get_user_by_email(session, email) is not None:
            raise ConflictError("An account with this email already exists.")

        user = User(
            email=email,
            display_name=display_name or None,
            role=role,
            is_approved=is_approved,
        )
        session.add(user)
        await session.flush()

        identity = AuthIdentity(
            user_id=user.id,
            provider=AuthProvider.credentials,
            password_hash=hash_password(password),
            password_algo=PASSWORD_ALGO,
        )
        session.add(identity)
        await session.commit()
        await session.refresh(user)
        return user

    async def approve_user(self, session: AsyncSession, user_id: UUID) -> User | None:
        """Set is_approved=True. Returns updated user or None if not found."""
        user = await session.get(User, user_id)
        if not user:
            return None
        user.is_approved = True
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def reject_user(self, session: AsyncSession, user_id: UUID) -> User | None:
        """Set is_approved=False. Returns updated user or None if not found."""
        user = await session.get(User, user_id)
        if not user:
            return None
        user.is_approved = False
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def update_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        email: str | None = None,
        display_name: str | None = None,
        avatar_url: str | None = None,
        role: UserRole | None = None,
        is_approved: bool | None = None,
        is_active: bool | None = None,
    ) -> User | None:
        """Update user by id. Only provided fields are updated."""
        user = await session.get(User, user_id)
        if not user:
            return None
        if email is not None:
            email = normalize_email(email)
            existing = await self._get_user_by_email(session, email)
            if existing is not None and existing.id != user_id:
                raise ConflictError("An account with this email already exists.")
            user.email = email
        if display_name is not None:
            user.display_name = display_name
        if avatar_url is not None:
            user.avatar_url = avatar_url
        if role is not None:
            user.role = role
        if is_approved is not None:
            user.is_approved = is_approved
        if is_active is not None:
            user.is_active = is_active
        user.updated_at = datetime.now(timezone.utc)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def delete_user(self, session: AsyncSession, user_id: UUID) -> bool:
        """Delete user and their identities. Returns True if deleted, False if not found."""
        user = await session.get(User, user_id)
        if not user:
            return False
        await session.delete(user)
        await session.commit()
        return True

    async def _get_user_by_email(self, session: AsyncSession, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await session.execute(statement)
        return result.scalars().first()


user_service = UserService()
