from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Account
from app.auth.security import decode_access_token
from app.common.database import get_db
from app.common.exceptions import ForbiddenException, UnauthorizedException


async def get_current_account(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> Account:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid authorization header")

    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)

    if not payload:
        raise UnauthorizedException("Invalid or expired token")

    account_id = int(payload.get("sub", 0))
    token_version = payload.get("tv", -1)

    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()

    if not account:
        raise UnauthorizedException("Account not found")

    if account.token_version != token_version:
        raise UnauthorizedException("Token has been revoked")

    return account


async def require_editor(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    if account.role not in ("editor", "admin"):
        raise ForbiddenException("Editor role required")
    return account


async def require_admin(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    if account.role != "admin":
        raise ForbiddenException("Admin role required")
    return account


CurrentAccount = Annotated[Account, Depends(get_current_account)]
EditorAccount = Annotated[Account, Depends(require_editor)]
AdminAccount = Annotated[Account, Depends(require_admin)]
