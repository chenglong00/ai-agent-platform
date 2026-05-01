"""Register all API routers on the app."""

from fastapi import FastAPI

from app.api.root import router as root_router
from app.api.v1.api import api_router
from app.core.config import settings


def setup_routers(app: FastAPI) -> None:
    """Include root and versioned API routers."""
    app.include_router(root_router)
    app.include_router(api_router, prefix=settings.API_V1_STR)
