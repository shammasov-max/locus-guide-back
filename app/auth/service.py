from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import Account, AuthIdentity, PasswordResetToken, RefreshToken
from app.auth.schemas import (
    AuthResponse,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserResponse,
)
from app.auth.security import (
    create_access_token,
    generate_password_reset_token,
    generate_refresh_token,
    get_password_reset_expiry,
    get_refresh_token_expiry,
    hash_password,
    hash_token,
    verify_password,
)
from app.common.config import settings
from app.common.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
)


async def get_account_by_email(db: AsyncSession, email: str) -> Account | None:
    result = await db.execute(
        select(Account)
        .options(selectinload(Account.auth_identities))
        .where(Account.email == email.lower())
    )
    return result.scalar_one_or_none()


async def get_account_by_id(db: AsyncSession, account_id: int) -> Account | None:
    result = await db.execute(
        select(Account)
        .options(selectinload(Account.auth_identities))
        .where(Account.id == account_id)
    )
    return result.scalar_one_or_none()


def build_user_response(account: Account) -> UserResponse:
    providers = [identity.provider for identity in account.auth_identities]
    return UserResponse(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        role=account.role,
        locale_pref=account.locale_pref,
        ui_lang=account.ui_lang,
        audio_lang=account.audio_lang,
        character=account.character,
        units=account.units,
        created_at=account.created_at,
        providers=providers,
    )


async def create_tokens(
    db: AsyncSession, account: Account, device_info: str | None = None
) -> TokenResponse:
    access_token = create_access_token(account.id, account.token_version)
    refresh_token_raw = generate_refresh_token()

    refresh_token = RefreshToken(
        account_id=account.id,
        token_hash=hash_token(refresh_token_raw),
        device_info=device_info,
        expires_at=get_refresh_token_expiry(),
    )
    db.add(refresh_token)
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_raw,
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def register_account(
    db: AsyncSession, request: RegisterRequest, device_info: str | None = None
) -> AuthResponse:
    existing = await get_account_by_email(db, request.email)
    if existing:
        raise ConflictException("Email already registered")

    account = Account(
        email=request.email.lower(),
        display_name=request.display_name,
        units=request.units,
    )
    db.add(account)
    await db.flush()

    identity = AuthIdentity(
        account_id=account.id,
        provider="email",
        provider_subject=request.email.lower(),
        email_verified=False,
        password_hash=hash_password(request.password),
    )
    db.add(identity)
    await db.flush()

    account.auth_identities = [identity]
    tokens = await create_tokens(db, account, device_info)

    return AuthResponse(user=build_user_response(account), tokens=tokens)


async def login_with_email(
    db: AsyncSession, email: str, password: str, device_info: str | None = None
) -> AuthResponse:
    account = await get_account_by_email(db, email)
    if not account:
        raise UnauthorizedException("Invalid email or password")

    email_identity = next(
        (i for i in account.auth_identities if i.provider == "email"), None
    )
    if not email_identity or not email_identity.password_hash:
        raise UnauthorizedException("Invalid email or password")

    if not verify_password(password, email_identity.password_hash):
        raise UnauthorizedException("Invalid email or password")

    tokens = await create_tokens(db, account, device_info)
    return AuthResponse(user=build_user_response(account), tokens=tokens)


async def login_with_google(
    db: AsyncSession, id_token: str, device_info: str | None = None
) -> AuthResponse:
    import httpx

    # Verify Google ID token
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
            )
            if response.status_code != 200:
                raise UnauthorizedException("Invalid Google token")
            token_info = response.json()
    except Exception:
        raise UnauthorizedException("Failed to verify Google token")

    if token_info.get("aud") != settings.google_client_id:
        raise UnauthorizedException("Invalid Google client ID")

    google_email = token_info.get("email", "").lower()
    google_sub = token_info.get("sub")
    email_verified = token_info.get("email_verified") == "true"

    if not google_email or not google_sub:
        raise BadRequestException("Invalid Google token payload")

    # Check for existing account
    account = await get_account_by_email(db, google_email)

    if account:
        # Check if Google identity already linked
        google_identity = next(
            (i for i in account.auth_identities if i.provider == "google"), None
        )
        if not google_identity:
            # Link Google to existing account
            google_identity = AuthIdentity(
                account_id=account.id,
                provider="google",
                provider_subject=google_sub,
                email_verified=email_verified,
            )
            db.add(google_identity)
            account.auth_identities.append(google_identity)
    else:
        # Create new account
        account = Account(
            email=google_email,
            display_name=token_info.get("name"),
        )
        db.add(account)
        await db.flush()

        google_identity = AuthIdentity(
            account_id=account.id,
            provider="google",
            provider_subject=google_sub,
            email_verified=email_verified,
        )
        db.add(google_identity)
        account.auth_identities = [google_identity]

    await db.flush()
    tokens = await create_tokens(db, account, device_info)
    return AuthResponse(user=build_user_response(account), tokens=tokens)


async def refresh_tokens(
    db: AsyncSession, refresh_token_raw: str, device_info: str | None = None
) -> TokenResponse:
    token_hash = hash_token(refresh_token_raw)

    result = await db.execute(
        select(RefreshToken)
        .options(selectinload(RefreshToken.account))
        .where(RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if not token:
        raise UnauthorizedException("Invalid refresh token")

    now = datetime.now(timezone.utc)
    if token.revoked_at or token.expires_at < now:
        raise UnauthorizedException("Refresh token expired or revoked")

    account = token.account
    if not account:
        raise UnauthorizedException("Account not found")

    # Revoke old token
    token.revoked_at = now
    await db.flush()

    # Issue new tokens
    return await create_tokens(db, account, device_info)


async def logout(db: AsyncSession, refresh_token_raw: str) -> None:
    token_hash = hash_token(refresh_token_raw)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if token:
        token.revoked_at = datetime.now(timezone.utc)
        await db.flush()


async def logout_all(db: AsyncSession, account: Account) -> None:
    account.token_version += 1

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.account_id == account.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    tokens = result.scalars().all()

    now = datetime.now(timezone.utc)
    for token in tokens:
        token.revoked_at = now

    await db.flush()


async def update_account(db: AsyncSession, account: Account, request: UpdateMeRequest) -> Account:
    if request.display_name is not None:
        account.display_name = request.display_name
    if request.units is not None:
        account.units = request.units
    if request.locale_pref is not None:
        account.locale_pref = request.locale_pref
    if request.ui_lang is not None:
        account.ui_lang = request.ui_lang
    if request.audio_lang is not None:
        account.audio_lang = request.audio_lang
    if request.character is not None:
        account.character = request.character

    await db.flush()
    await db.refresh(account, ["auth_identities"])
    return account


async def delete_account(db: AsyncSession, account: Account) -> None:
    await db.delete(account)
    await db.flush()


async def request_password_reset(db: AsyncSession, email: str) -> None:
    account = await get_account_by_email(db, email)
    if not account:
        return  # Always return success to prevent email enumeration

    email_identity = next(
        (i for i in account.auth_identities if i.provider == "email"), None
    )
    if not email_identity:
        return

    token_raw = generate_password_reset_token()
    reset_token = PasswordResetToken(
        identity_id=email_identity.id,
        token_hash=hash_token(token_raw),
        expires_at=get_password_reset_expiry(),
    )
    db.add(reset_token)
    await db.flush()

    # TODO: Send email with token_raw
    # For now, we just create the token


async def confirm_password_reset(db: AsyncSession, token_raw: str, new_password: str) -> None:
    token_hash = hash_token(token_raw)

    result = await db.execute(
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.identity))
        .where(PasswordResetToken.token_hash == token_hash)
    )
    reset_token = result.scalar_one_or_none()

    if not reset_token:
        raise NotFoundException("Invalid or expired reset token")

    now = datetime.now(timezone.utc)
    if reset_token.used_at or reset_token.expires_at < now:
        raise BadRequestException("Reset token expired or already used")

    reset_token.used_at = now
    reset_token.identity.password_hash = hash_password(new_password)
    await db.flush()
