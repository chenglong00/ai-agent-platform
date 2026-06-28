from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.environment import get_env_files
from app.core.secrets import prepare_secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=get_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # ignore env vars that are not Settings fields (e.g. APP_ENV, debug)
    )

    APPLICATION_NAME: str = "backend-fastapi"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "Add your description here"
    # Used for SQL echo and similar; not in pydantic field name (env: DEBUG).
    DEBUG: bool = False
    # HS256 requires at least 32 bytes (RFC 7518). Override via env SECRET_KEY.
    SECRET_KEY: str = "your-secret-key-must-be-at-least-32-characters-long"
    # Optional: previous key for rotation. Set after rotating SECRET_KEY so existing JWTs still verify; remove after they expire.
    SECRET_KEY_PREVIOUS: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Comma-separated origins. Stored as str so pydantic-settings does not coerce before parsing.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        return [
            x.strip() for x in self.ALLOWED_ORIGINS.strip().split(",") if x.strip()
        ]

    # Rate limit (slowapi): default per-route limit, e.g. "100/minute", "10/second"
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # API Versioning: set API_V1_STR env as the API version prefix (e.g. "/api/v1")
    API_V1_STR: str = "/api/v1"

    # Logging: console=pretty; file = daily JSONL under LOG_DIR when set, else single file if LOG_FILE set
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = Path("")
    LOG_FILE: str = ""
    TIMEZONE: str = "UTC"

    DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    MONGODB_URI: str = ""
    KNOWLEDGE_BASE_UPLOAD_DIR: Path = Path("data/knowledge_base")

    # Initial owner (optional): set env to create an OWNER user and credentials identity on first run
    INITIAL_OWNER_EMAIL: str = ""
    INITIAL_OWNER_PASSWORD: str = ""
    INITIAL_OWNER_NAME: str = ""

    # Google OAuth2 (optional). If set, GET /oauth/google/authorize and /oauth/google/callback are enabled.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Must match the redirect URI in Google Cloud Console (e.g. http://localhost:8000/api/v1/oauth/google/callback)
    GOOGLE_REDIRECT_URI: str = ""
    # Where to redirect the user after successful Google login (e.g. http://localhost:3000/login/callback). Token is appended as ?token=...
    AUTH_SUCCESS_REDIRECT_URL: str = ""
    # Extra Google OAuth scopes (space-separated). e.g. "https://www.googleapis.com/auth/calendar.readonly" for Calendar. Base "openid email profile" are always included.
    GOOGLE_EXTRA_SCOPES: str = ""

    # Optional: 32+ char key or Fernet base64 key to encrypt OAuth tokens at rest. If unset, tokens are stored plaintext (not recommended for production).
    ENCRYPTION_KEY: str = ""
    # Optional: previous key for rotation. Set after rotating ENCRYPTION_KEY so existing ciphertext still decrypts; remove after re-encryption.
    ENCRYPTION_KEY_PREVIOUS: str = ""

    # Deep agent backend: "local" | "daytona" | "modal"
    DEEP_AGENT_BACKEND: str = "local"
    # Working directory inside the sandbox the agent operates in.
    DEEP_AGENT_SANDBOX_WORKDIR: str = "/workspace"
    # Host directory for per-user local sandboxes (DEEP_AGENT_BACKEND=local).
    DEEP_AGENT_SANDBOX_LOCAL_ROOT: Path = Path("data/agent_sandboxes")
    # Idle TTL for pooled user sandboxes; 0 disables automatic cleanup.
    DEEP_AGENT_SANDBOX_IDLE_TTL_SECONDS: int = 3600
    DEEP_AGENT_SANDBOX_CLEANUP_INTERVAL_SECONDS: int = 300
    # Modal (DEEP_AGENT_BACKEND=modal): requires MODAL_TOKEN_ID and MODAL_TOKEN_SECRET.
    DEEP_AGENT_MODAL_APP: str = "ai-application-platform-deep-agent"
    MODAL_TOKEN_ID: str = ""
    MODAL_TOKEN_SECRET: str = ""
    # Daytona (DEEP_AGENT_BACKEND=daytona): requires DAYTONA_API_KEY.
    DAYTONA_API_KEY: str = ""
    DAYTONA_TARGET: str = "us"
    DAYTONA_API_URL: str = ""

    # Playwright browser tools (per-user pooled Chromium sessions)
    BROWSER_PLAYWRIGHT_ENABLED: bool = False
    BROWSER_PLAYWRIGHT_HEADLESS: bool = True
    BROWSER_PLAYWRIGHT_TIMEOUT_MS: int = 30_000
    BROWSER_PLAYWRIGHT_VIEWPORT_WIDTH: int = 1280
    BROWSER_PLAYWRIGHT_VIEWPORT_HEIGHT: int = 720
    BROWSER_PLAYWRIGHT_READ_MAX_CHARS: int = 4000
    BROWSER_PLAYWRIGHT_IDLE_TTL_SECONDS: int = 1800
    BROWSER_PLAYWRIGHT_LIVE_ENABLED: bool = True
    BROWSER_PLAYWRIGHT_LIVE_MAX_FPS: int = 12
    BROWSER_PLAYWRIGHT_LIVE_JPEG_QUALITY: int = 65


def prepare_settings() -> Settings:
    """Load secrets into env (e.g. from a secret manager), then create and return Settings.
    See docs/SECRETS.md. Add any other pre-Settings setup here."""
    prepare_secrets()
    return Settings()


settings = prepare_settings()