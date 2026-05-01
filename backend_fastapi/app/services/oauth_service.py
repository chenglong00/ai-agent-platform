"""OAuth callback business logic: userinfo from token, create/link user, return JWT. Provider-agnostic."""

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import AuthProvider
from app.services.auth_service import auth_service
from app.utils.validation import normalize_email

# Provider name -> userinfo URL (GET with Bearer token). Add entries when adding new OAuth providers.
USERINFO_URLS: dict[str, str] = {
    "google": "https://openidconnect.googleapis.com/v1/userinfo",
    # "github": "https://api.github.com/user",
    # "microsoft": "https://graph.microsoft.com/v1.0/me",
}


class OAuthService:
    """Complete OAuth login per provider: userinfo from token, create/link user, return JWT."""

    async def _fetch_userinfo(self, provider: str, access_token: str) -> dict:
        """Fetch userinfo from the given provider. Returns raw provider response (shape varies by provider)."""
        url = USERINFO_URLS.get(provider)
        if not url:
            raise ValueError(f"Unknown OAuth provider: {provider}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})
        resp.raise_for_status()
        return resp.json()

    async def complete_login(self, session: AsyncSession, token: dict, provider: str) -> str:
        """Run provider-specific login flow. Returns JWT. Raises ValueError for invalid userinfo, AuthenticationError if user disabled."""
        if provider == "google":
            return await self._complete_google(session, token)
        raise ValueError(f"Unsupported OAuth provider: {provider}")

    async def _complete_google(self, session: AsyncSession, token: dict) -> str:
        """Get userinfo from token (or fetch), create or link user, return JWT."""
        userinfo = token.get("userinfo")
        if not userinfo:
            access_token = token.get("access_token")
            if not access_token:
                raise ValueError("No access_token in Google response")
            try:
                userinfo = await self._fetch_userinfo("google", access_token)
            except httpx.HTTPError:
                raise ValueError("Failed to fetch Google user info")

        google_id = userinfo.get("sub")
        email = userinfo.get("email")
        if not google_id or not email:
            raise ValueError("Google did not return sub or email")

        email = normalize_email(email)
        name = userinfo.get("name") or userinfo.get("given_name")
        picture = userinfo.get("picture")

        return await auth_service.login_or_register_oauth(
            session,
            provider=AuthProvider.google,
            provider_user_id=google_id,
            email=email,
            name=name,
            picture=picture,
        )


oauth_service = OAuthService()
