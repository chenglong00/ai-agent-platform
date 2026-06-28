"""OAuth routes: external providers (Google, etc.). Authlib + session for state."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request
from typing import Annotated
from app.core.config import settings
from app.core.dependency import get_db
from app.core.exceptions import AuthenticationError
from app.core.oauth import build_auth_success_redirect_url, get_oauth, is_google_oauth_configured
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
    """Exchange the authorization code (Authlib validates state), get userinfo, create or link user, redirect with JWT."""
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
        access_token_jwt = await oauth_service.complete_login(session, token, "google")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError:
        raise HTTPException(status_code=403, detail="Account is disabled or not allowed")

    return RedirectResponse(url=build_auth_success_redirect_url(access_token_jwt))
