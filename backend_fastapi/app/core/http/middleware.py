"""Session, CORS, and request-context middleware."""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.observability.logging import (
    endpoint_ctx,
    request_id_ctx,
    status_code_ctx,
    user_id_ctx,
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Populate logging context vars for each HTTP request."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        rid_token = request_id_ctx.set(request_id)
        ep_token = endpoint_ctx.set(f"{request.method} {request.url.path}")
        uid_token = user_id_ctx.set(None)
        sc_token = status_code_ctx.set(None)
        try:
            response = await call_next(request)
            status_code_ctx.set(response.status_code)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(rid_token)
            endpoint_ctx.reset(ep_token)
            user_id_ctx.reset(uid_token)
            status_code_ctx.reset(sc_token)


def setup_middleware(app: FastAPI) -> None:
    """Register middleware. CORSMiddleware last so it wraps the stack outermost."""
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
