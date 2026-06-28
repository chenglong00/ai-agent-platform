"""FastAPI dependency providers for route injection (e.g. Depends(get_db))."""

from collections.abc import AsyncGenerator

from sqlmodel.ext.asyncio.session import AsyncSession


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async session for dependency injection. Use with Depends(get_db) in route handlers.
    Route handlers should call await session.commit() after making changes. On exception the session is rolled back;
    the session is closed when the request ends."""
    from app.core.db.postgres import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
