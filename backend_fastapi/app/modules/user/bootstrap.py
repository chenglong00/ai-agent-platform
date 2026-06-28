"""Startup bootstrap for the user module (e.g. initial owner seeding)."""

import logging

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.db.postgres import get_async_session_factory
from app.core.security.password import PASSWORD_ALGO, hash_password
from app.modules.auth.model import AuthIdentity, AuthProvider
from app.modules.user.model import User, UserRole

logger = logging.getLogger(__name__)


async def ensure_initial_owner() -> None:
    """Create initial OWNER user when INITIAL_OWNER_EMAIL is set."""
    factory = get_async_session_factory()
    email = (settings.INITIAL_OWNER_EMAIL or "").strip().lower()
    if not email:
        return

    async with factory() as session:
        await _create_initial_owner_if_missing(session, email)


async def _create_initial_owner_if_missing(session: AsyncSession, email: str) -> None:
    result = await session.execute(select(User).where(User.email == email))
    if result.scalars().first():
        return

    user = User(
        email=email,
        display_name=(settings.INITIAL_OWNER_NAME or "").strip() or None,
        role=UserRole.OWNER,
        is_approved=True,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    password = (settings.INITIAL_OWNER_PASSWORD or "").strip()
    if password:
        session.add(
            AuthIdentity(
                user_id=user.id,
                provider=AuthProvider.credentials,
                password_hash=hash_password(password),
                password_algo=PASSWORD_ALGO,
            )
        )
    await session.commit()
    logger.info("initial_owner_created", extra={"email": email})
