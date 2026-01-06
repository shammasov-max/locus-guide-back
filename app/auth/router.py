from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.dependencies import CurrentAccount
from app.auth.schemas import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserResponse,
)
from app.common.database import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> AuthResponse:
    return await service.register_account(db, request, user_agent)


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> AuthResponse:
    return await service.login_with_email(db, request.email, request.password, user_agent)


@router.post("/google", response_model=AuthResponse)
async def google_auth(
    request: GoogleAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> AuthResponse:
    return await service.login_with_google(db, request.id_token, user_agent)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    return await service.refresh_tokens(db, request.refresh_token, user_agent)


@router.post("/password-reset/request", response_model=MessageResponse)
async def password_reset_request(
    request: PasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await service.request_password_reset(db, request.email)
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def password_reset_confirm(
    request: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await service.confirm_password_reset(db, request.token, request.new_password)
    return MessageResponse(message="Password has been reset successfully")


@router.get("/me", response_model=UserResponse)
async def get_me(account: CurrentAccount) -> UserResponse:
    return service.build_user_response(account)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: UpdateMeRequest,
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    updated = await service.update_account(db, account, request)
    return service.build_user_response(updated)


@router.delete("/me", response_model=MessageResponse)
async def delete_me(
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await service.delete_account(db, account)
    return MessageResponse(message="Account deleted successfully")


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: LogoutRequest,
    _: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await service.logout(db, request.refresh_token)
    return MessageResponse(message="Logged out successfully")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    account: CurrentAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await service.logout_all(db, account)
    return MessageResponse(message="Logged out from all devices")
