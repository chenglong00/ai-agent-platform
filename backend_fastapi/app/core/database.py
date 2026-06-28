import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.environment import get_environment
from app.core.password import PASSWORD_ALGO, hash_password
import app.modules.models  # noqa: F401 — register all ORM mappers before queries
from app.modules.auth.model import AuthIdentity, AuthProvider
from app.modules.user.model import User, UserRole

logger = logging.getLogger(__name__)
engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_engine() -> None:
    """Create and store the global async database engine (connection pool)."""
    global engine, async_session_factory

    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    # Use an async driver in DATABASE_URL (e.g. postgresql+asyncpg:// for PostgreSQL).
    try:
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_pre_ping=True,
            pool_size=getattr(settings, "DB_POOL_SIZE", 5),
            max_overflow=getattr(settings, "DB_MAX_OVERFLOW", 10),
            pool_timeout=30,
            pool_recycle=1800,
        )

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        logger.info(
            "database_engine_initialized",
            extra={"environment": get_environment().value},
        )

    except SQLAlchemyError as e:
        logger.critical("database_connection_failed", extra={"error": str(e)})
        raise RuntimeError("Application startup failed: Could not connect to the database.") from e


async def close_engine() -> None:
    """Dispose the global engine and its connection pool."""
    global engine, async_session_factory
    if engine:
        await engine.dispose()
        engine = None
        async_session_factory = None
        logger.info("database_engine_closed")


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory. Use: async with get_async_session_factory()() as session."""
    if not async_session_factory:
        raise RuntimeError("Database engine is not initialized. Call init_engine() first.")
    return async_session_factory


async def ensure_initial_owner() -> None:
    """Create initial OWNER user and credentials identity only when INITIAL_OWNER_EMAIL (and optionally INITIAL_OWNER_PASSWORD) are set. If not set, no owner is created and startup continues normally."""
    if not async_session_factory:
        raise RuntimeError("Database engine is not initialized. Call init_engine() first.")
    email = (settings.INITIAL_OWNER_EMAIL or "").strip().lower()
    if not email:
        return

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalars().first()
        if existing:
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
            identity = AuthIdentity(
                user_id=user.id,
                provider=AuthProvider.credentials,
                password_hash=hash_password(password),
                password_algo=PASSWORD_ALGO,
            )
            session.add(identity)
        await session.commit()
        logger.info("initial_owner_created", extra={"email": email})


async def check_database() -> bool:
    """Return True if the database is reachable, False otherwise."""
    if not async_session_factory:
        return False
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error("database_health_check_failed", extra={"error": str(e)})
        return False
