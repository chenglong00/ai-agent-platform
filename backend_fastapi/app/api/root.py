"""Root and health-style routes (no version prefix)."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/")
async def root():
    """API info and links. Use /docs for Swagger UI."""
    return {
        "name": settings.APPLICATION_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "api": settings.API_V1_STR,
    }
