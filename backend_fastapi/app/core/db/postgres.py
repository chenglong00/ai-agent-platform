import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.db.registry import register_models
from app.core.environment import get_environment

register_models()

logger = logging.getLogger(__name__)
engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_engine() -> None:
    """Create and store the global async database engine (connection pool)."""
    global engine, async_session_factory

    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    try:
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_pre_ping=True,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
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
