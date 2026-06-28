from fastapi import FastAPI

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.http.limiter import setup_limiter
from app.core.http.middleware import setup_middleware
from app.core.http.router import setup_routers
from app.core.lifespan import lifespan
from app.core.observability.logging import configure_logging
from app.core.observability.metrics import setup_metrics
from app.core.security.oauth import setup_oauth

configure_logging(
    level=settings.LOG_LEVEL,
    service_name=settings.APPLICATION_NAME,
    log_file=settings.LOG_FILE or "",
)

app = FastAPI(
    title=settings.APPLICATION_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
)

setup_limiter(app)
register_exception_handlers(app)
setup_middleware(app)
setup_oauth(app)
setup_metrics(app)
setup_routers(app)
