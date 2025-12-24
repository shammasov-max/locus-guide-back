import httpx

from app.common.exceptions import GoogleAuthException
from app.config import get_settings

settings = get_settings()

GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


async def verify_google_token(id_token: str) -> dict:
    """
    Verify Google ID token and return user info.

    The token is verified by calling Google's tokeninfo endpoint.
    For mobile apps, the id_token is obtained from Google Sign-In SDK.

    Returns a dict with:
    - sub: Google user ID (unique identifier)
    - email: User's email (may be None if not shared)
    - email_verified: Whether email is verified
    - name: User's display name
    - picture: Profile picture URL
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                GOOGLE_TOKEN_INFO_URL,
                params={"id_token": id_token},
                timeout=10.0,
            )
        except httpx.RequestError as e:
            raise GoogleAuthException(f"Failed to verify Google token: {str(e)}")

        if response.status_code != 200:
            raise GoogleAuthException("Invalid Google token")

        data = response.json()

        # Verify the token was issued for our app
        if settings.google_client_id and data.get("aud") != settings.google_client_id:
            raise GoogleAuthException("Token was not issued for this application")

        # Check token is not expired (tokeninfo already validates this, but double-check)
        if "error" in data:
            raise GoogleAuthException(data.get("error_description", "Invalid token"))

        return {
            "sub": data["sub"],
            "email": data.get("email"),
            "email_verified": data.get("email_verified", "false") == "true",
            "name": data.get("name"),
            "picture": data.get("picture"),
        }
