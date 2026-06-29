"""Application lifespan: startup and shutdown.

Use for initializing and cleaning up resources (DB, caches, etc.).
Add logic above the yield for startup, below for shutdown.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db.postgres import close_engine, init_engine
from app.core.environment import is_test_env
from app.core.observability.langfuse import flush_langfuse, init_langfuse
from app.core.observability.logging import align_uvicorn_with_root
from app.ai.chat_agent.backend_factory import (
    shutdown_all_sandboxes,
    start_sandbox_cleanup_loop,
    stop_sandbox_cleanup_loop,
)
from app.ai.chat_agent.playwright_pool import shutdown_all_browsers
from app.modules.knowledge_base.client import close_mongodb, init_mongodb
from app.modules.user.bootstrap import ensure_initial_owner
from app.modules.workflow.scheduler import start_workflow_scheduler, stop_workflow_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown. Add DB connect, logging, etc. above yield; cleanup below."""
    align_uvicorn_with_root()
    if not is_test_env():
        init_langfuse()
        await init_engine()
        await ensure_initial_owner()
        await init_mongodb()
        start_sandbox_cleanup_loop()
        start_workflow_scheduler()

    yield

    if not is_test_env():
        flush_langfuse()
        await stop_workflow_scheduler()
        await stop_sandbox_cleanup_loop()
        await shutdown_all_browsers()
        await asyncio.to_thread(shutdown_all_sandboxes)
        await close_mongodb()
        await close_engine()
