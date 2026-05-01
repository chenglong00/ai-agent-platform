"""Aggregate v1 API routes. Include routers here, e.g. api_router.include_router(users.router, prefix="/users")."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.group import router as group_router
from app.api.v1.oauth import router as oauth_router
from app.api.v1.workspace import router as workspace_router

api_router = APIRouter()

api_router.include_router(admin_router, prefix="/admin")
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(oauth_router, prefix="/oauth", tags=["oauth"])
api_router.include_router(group_router, prefix="/groups", tags=["groups"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(workspace_router, prefix="/workspace", tags=["workspace"])
