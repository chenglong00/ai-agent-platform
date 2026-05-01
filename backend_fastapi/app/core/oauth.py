"""OAuth client (Authlib) for external providers. Initialized at app startup."""

from fastapi import FastAPI
from starlette.requests import Request

from app.core.config import settings


def get_oauth(request: Request):
    """FastAPI dependency: return the OAuth instance from app.state. Use with Depends(get_oauth)."""
    return request.app.state.oauth


def build_auth_success_redirect_url(token: str) -> str:
    """Build the URL to redirect to after successful OAuth login, with the JWT appended as query param."""
    base = settings.AUTH_SUCCESS_REDIRECT_URL or "/"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}token={token}"


def is_google_oauth_configured() -> bool:
    """Return True if Google OAuth env vars are set (client_id, client_secret, redirect_uri)."""
    return bool(
        settings.GOOGLE_CLIENT_ID
        and settings.GOOGLE_CLIENT_SECRET
        and settings.GOOGLE_REDIRECT_URI
    )


def setup_oauth(app: FastAPI) -> None:
    """Register OAuth providers and attach to app.state.oauth. Call once at startup."""
    from authlib.integrations.starlette_client import OAuth

    oauth = OAuth()

    if is_google_oauth_configured():
        scopes = "openid email profile"
        
        if settings.GOOGLE_EXTRA_SCOPES:
            scopes += " " + settings.GOOGLE_EXTRA_SCOPES.strip()

        oauth.register(
            name="google",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": scopes},
        )
    # Add more providers here (e.g. oauth.register(name="github", ...)) when configured.

    app.state.oauth = oauth
