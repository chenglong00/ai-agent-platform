"""Aggregate v1 API routes from domain modules."""

from fastapi import APIRouter

from app.modules.user.router import router as admin_router
from app.modules.auth.oauth_router import router as oauth_router
from app.modules.auth.router import router as auth_router
from app.modules.chat.router import router as chat_router
from app.modules.group.router import router as group_router
from app.modules.knowledge_base.router import router as knowledge_base_router
from app.modules.memory.router import router as memory_router
from app.modules.skills.router import router as skills_router
from app.modules.workspace.router import router as workspace_router

api_router = APIRouter()

api_router.include_router(admin_router, prefix="/admin")
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(oauth_router, prefix="/oauth", tags=["oauth"])
api_router.include_router(group_router, prefix="/groups", tags=["groups"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(
    knowledge_base_router,
    prefix="/knowledge-base",
    tags=["knowledge-base"],
)
api_router.include_router(
    skills_router,
    prefix="/skills",
    tags=["skills"],
)
api_router.include_router(
    memory_router,
    prefix="/memory",
    tags=["memory"],
)
api_router.include_router(workspace_router, prefix="/workspace", tags=["workspace"])
