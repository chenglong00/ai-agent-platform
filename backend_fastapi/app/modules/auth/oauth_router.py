"""OAuth routes: external providers (Google, etc.). Authlib + session for state."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request
from typing import Annotated
from app.core.config import settings
from app.core.security.dependencies import get_db
from app.core.security.oauth import build_auth_success_redirect_url, get_oauth, is_google_oauth_configured
from app.modules.auth.cookies import set_auth_cookies
from app.modules.auth.oauth_service import oauth_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/google")
async def google_login(request: Request, oauth=Depends(get_oauth)):
    """Redirect the user to Google's consent screen. Uses Authlib (state stored in session)."""
    if not is_google_oauth_configured():
        raise HTTPException(
            status_code=503,
            detail="Google login is not configured (set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)",
        )
    return await oauth.google.authorize_redirect(request, settings.GOOGLE_REDIRECT_URI)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    oauth=Depends(get_oauth),
):
    """Exchange code, create or link user, set auth cookies, redirect to frontend."""
    if not is_google_oauth_configured():
        raise HTTPException(
            status_code=503,
            detail="Google login is not configured (set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)",
        )

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        logger.warning("Google OAuth token exchange failed: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    try:
        tokens = await oauth_service.complete_login(session, token, "google")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    response = RedirectResponse(url=build_auth_success_redirect_url(), status_code=302)
    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )
    return response
