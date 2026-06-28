"""Per-route rate limiter (slowapi).

Use in routes with the decorator (request must be in the route):

    from app.core.http.limiter import limiter

    @router.get("/login")
    @limiter.limit("5/minute")
    async def login(request: Request):
        ...
"""

from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)


def setup_limiter(app: FastAPI) -> None:
    """Attach limiter to app state and register RateLimitExceeded exception handler."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
