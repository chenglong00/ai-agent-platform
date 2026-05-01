from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.lifespan import lifespan
from app.core.limiter import setup_limiter
from app.core.metrics import setup_metrics
from app.core.middleware import setup_middleware
from app.core.oauth import setup_oauth
from app.core.router import setup_routers

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
setup_middleware(app)
setup_oauth(app)
setup_metrics(app)
setup_routers(app)