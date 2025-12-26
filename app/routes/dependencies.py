from typing import Annotated
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import AppUser
from app.routes.service import RouteService


def get_route_service(db: Session = Depends(get_db)) -> RouteService:
    return RouteService(db)


security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> AppUser | None:
    """Get current user if authenticated, None otherwise"""
    if credentials is None:
        return None
    try:
        # Import here to avoid circular imports
        from app.auth.security import decode_access_token
        from app.auth.models import AppUser

        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        token_version = payload.get("tv")

        user = db.query(AppUser).filter(AppUser.id == int(user_id)).first()
        if user is None or user.token_version != token_version:
            return None
        return user
    except Exception:
        return None


RouteServiceDep = Annotated[RouteService, Depends(get_route_service)]
CurrentUserOptional = Annotated[AppUser | None, Depends(get_current_user_optional)]
CurrentUser = Annotated[AppUser, Depends(get_current_user)]
