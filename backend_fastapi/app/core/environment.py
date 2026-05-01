"""Environment detection and the Environment enum.

Use get_environment() to read APP_ENV. Use get_env_files() for Settings env_file
(e.g. in config.py). Loads base .env files first so APP_ENV is set, then returns
base + env-specific paths.
"""

import logging
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
_BASE_DIR = Path(__file__).resolve().parents[2]


class Environment(str, Enum):
    """Application environment types.

    Defines the possible environments the application can run in:
    local, development, UAT, production, and test.
    """
    LOCAL = "local"  # Local development
    DEVELOPMENT = "dev"  # SIT / development environment
    UAT = "uat"  # Staging environment
    PRODUCTION = "prod"  # Production environment
    TEST = "test"  # Unit testing; bypasses DB and other services


# All valid APP_ENV values (canonical + aliases) -> Environment
_APP_ENV_MAP: dict[str, Environment] = {
    "local": Environment.LOCAL,
    "development": Environment.DEVELOPMENT,
    "dev": Environment.DEVELOPMENT,
    "uat": Environment.UAT,
    "staging": Environment.UAT,
    "stage": Environment.UAT,
    "production": Environment.PRODUCTION,
    "prod": Environment.PRODUCTION,
    "test": Environment.TEST,
    "testing": Environment.TEST,
}


@lru_cache(maxsize=1)
def get_environment() -> Environment:
    """Return the current environment from APP_ENV (default: local). Cached per process.
    In tests, call get_environment.cache_clear() if you change APP_ENV."""
    env_value = os.getenv("APP_ENV", "local").lower().strip()
    env = _APP_ENV_MAP.get(env_value)
    if env is not None:
        return env
    logger.warning("Unknown APP_ENV=%r, defaulting to LOCAL", env_value)
    return Environment.LOCAL


def get_env_files() -> tuple[Path, ...]:
    """Load base .env files so APP_ENV is set, then return env file list for Settings.
    Order: base first, then env-specific (later override earlier)."""
    load_dotenv(_BASE_DIR / ".env") # by default override = False
    load_dotenv(_BASE_DIR / ".env.local")
    env = get_environment()
    return (
        _BASE_DIR / ".env",
        _BASE_DIR / ".env.local",
        _BASE_DIR / f".env.{env.value}",
        _BASE_DIR / f".env.{env.value}.local",
    )


def is_test_env() -> bool:
    """Return True when APP_ENV is test (e.g. skip DB in lifespan)."""
    return get_environment() == Environment.TEST
