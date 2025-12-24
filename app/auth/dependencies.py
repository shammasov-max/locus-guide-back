from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import AppUser
from app.auth.security import decode_access_token
from app.auth.service import AuthService
from app.common.exceptions import InvalidTokenException
from app.database import get_db

security = HTTPBearer()


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> AppUser:
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise InvalidTokenException()

    user_id = int(payload["sub"])
    token_version = payload.get("tv", 0)

    user = auth_service.get_user_by_id(user_id)

    if not user:
        raise InvalidTokenException()

    # Check token version (for logout-all functionality)
    if user.token_version != token_version:
        raise InvalidTokenException()

    return user


def get_device_info(
    user_agent: Annotated[str | None, Header()] = None,
) -> str | None:
    return user_agent


# Type aliases for cleaner route signatures
CurrentUser = Annotated[AppUser, Depends(get_current_user)]
DeviceInfo = Annotated[str | None, Depends(get_device_info)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
