"""Application lifespan: startup and shutdown.

Use for initializing and cleaning up resources (DB, caches, etc.).
Add logic above the yield for startup, below for shutdown.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import close_engine, init_engine, ensure_initial_owner
from app.core.environment import is_test_env
from app.core.logging import align_uvicorn_with_root


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown. Add DB connect, logging, etc. above yield; cleanup below."""
    align_uvicorn_with_root()
    # Startup (skip DB only when APP_ENV=test/testing so tests can run without a real DB)
    if not is_test_env():
        await init_engine()
        await ensure_initial_owner()

    yield

    # Shutdown
    if not is_test_env():
        await close_engine()
