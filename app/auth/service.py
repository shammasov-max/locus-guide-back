from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AppUser, AuthIdentity, PasswordResetToken, RefreshToken
from app.auth.schemas import (
    AuthResponse,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.auth.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.common.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    UserExistsException,
    UserNotFoundException,
)
from app.config import get_settings

settings = get_settings()


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def _get_user_providers(self, user: AppUser) -> list[str]:
        return [identity.provider for identity in user.identities]

    def _create_tokens(
        self, user: AppUser, device_info: str | None = None
    ) -> TokenResponse:
        # Create access token
        access_token = create_access_token(user.id, user.token_version)

        # Create refresh token
        raw_token, hashed_token, expires_at = create_refresh_token()

        # Store refresh token in DB
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=hashed_token,
            device_info=device_info,
            expires_at=expires_at,
        )
        self.db.add(refresh_token)
        self.db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    def _build_user_response(self, user: AppUser) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            locale_pref=user.locale_pref,
            ui_lang=user.ui_lang,
            audio_lang=user.audio_lang,
            units=user.units,
            created_at=user.created_at,
            providers=self._get_user_providers(user),
        )

    def _build_auth_response(
        self, user: AppUser, device_info: str | None = None
    ) -> AuthResponse:
        tokens = self._create_tokens(user, device_info)
        return AuthResponse(
            user=self._build_user_response(user),
            tokens=tokens,
        )

    def _find_user_by_email(self, email: str) -> AppUser | None:
        stmt = select(AppUser).where(AppUser.email == email.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def _find_identity_by_provider(
        self, provider: str, provider_subject: str
    ) -> AuthIdentity | None:
        stmt = select(AuthIdentity).where(
            AuthIdentity.provider == provider,
            AuthIdentity.provider_subject == provider_subject,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def register(
        self, data: RegisterRequest, device_info: str | None = None
    ) -> AuthResponse:
        email = data.email.lower()

        # Check if user already exists with this email
        existing_user = self._find_user_by_email(email)
        if existing_user:
            # Check if email identity already exists
            existing_identity = self._find_identity_by_provider("email", email)
            if existing_identity:
                raise UserExistsException()

            # User exists (probably via Google), add email identity
            identity = AuthIdentity(
                user_id=existing_user.id,
                provider="email",
                provider_subject=email,
                email_verified=False,
                password_hash=hash_password(data.password),
            )
            self.db.add(identity)
            self.db.commit()
            self.db.refresh(existing_user)
            return self._build_auth_response(existing_user, device_info)

        # Create new user
        user = AppUser(
            email=email,
            display_name=data.display_name,
            locale_pref=data.locale_pref,
            ui_lang=data.ui_lang,
            audio_lang=data.audio_lang,
            units=data.units,
        )
        self.db.add(user)
        self.db.flush()  # Get user.id

        # Create email identity
        identity = AuthIdentity(
            user_id=user.id,
            provider="email",
            provider_subject=email,
            email_verified=False,
            password_hash=hash_password(data.password),
        )
        self.db.add(identity)
        self.db.commit()
        self.db.refresh(user)

        return self._build_auth_response(user, device_info)

    def login(
        self, email: str, password: str, device_info: str | None = None
    ) -> AuthResponse:
        email = email.lower()

        # Find email identity
        identity = self._find_identity_by_provider("email", email)
        if not identity or not identity.password_hash:
            raise InvalidCredentialsException()

        # Verify password
        if not verify_password(password, identity.password_hash):
            raise InvalidCredentialsException()

        # Rehash password if needed (Argon2 parameter upgrade)
        if needs_rehash(identity.password_hash):
            identity.password_hash = hash_password(password)
            self.db.commit()

        return self._build_auth_response(identity.user, device_info)

    def google_auth(
        self,
        google_sub: str,
        email: str | None,
        email_verified: bool,
        display_name: str | None = None,
        locale_pref: str | None = None,
        ui_lang: str | None = None,
        audio_lang: str | None = None,
        units: str = "metric",
        device_info: str | None = None,
    ) -> AuthResponse:
        # Check if Google identity already exists
        existing_identity = self._find_identity_by_provider("google", google_sub)
        if existing_identity:
            return self._build_auth_response(existing_identity.user, device_info)

        # Check if user with this email already exists (auto-merge)
        if email:
            email = email.lower()
            existing_user = self._find_user_by_email(email)
            if existing_user:
                # Add Google identity to existing user
                identity = AuthIdentity(
                    user_id=existing_user.id,
                    provider="google",
                    provider_subject=google_sub,
                    email_verified=email_verified,
                )
                self.db.add(identity)
                self.db.commit()
                self.db.refresh(existing_user)
                return self._build_auth_response(existing_user, device_info)

        # Create new user
        user = AppUser(
            email=email,
            display_name=display_name,
            locale_pref=locale_pref,
            ui_lang=ui_lang,
            audio_lang=audio_lang,
            units=units,
        )
        self.db.add(user)
        self.db.flush()

        # Create Google identity
        identity = AuthIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=google_sub,
            email_verified=email_verified,
        )
        self.db.add(identity)
        self.db.commit()
        self.db.refresh(user)

        return self._build_auth_response(user, device_info)

    def refresh_tokens(
        self, refresh_token: str, device_info: str | None = None
    ) -> TokenResponse:
        token_hash = hash_token(refresh_token)

        # Find the refresh token
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        db_token = self.db.execute(stmt).scalar_one_or_none()

        if not db_token:
            raise InvalidTokenException()

        user = db_token.user

        # Check token version (for logout-all functionality)
        # We can't check token version against refresh token directly,
        # but we can revoke all tokens when logout-all is called

        # Revoke old refresh token
        db_token.revoked_at = datetime.now(timezone.utc)

        # Create new tokens
        tokens = self._create_tokens(user, device_info)
        self.db.commit()

        return tokens

    def logout(self, refresh_token: str) -> None:
        token_hash = hash_token(refresh_token)

        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        db_token = self.db.execute(stmt).scalar_one_or_none()

        if db_token and not db_token.revoked_at:
            db_token.revoked_at = datetime.now(timezone.utc)
            self.db.commit()

    def logout_all(self, user_id: int) -> None:
        # Increment token version to invalidate all access tokens
        stmt = select(AppUser).where(AppUser.id == user_id)
        user = self.db.execute(stmt).scalar_one_or_none()

        if user:
            user.token_version += 1

            # Revoke all refresh tokens
            for token in user.refresh_tokens:
                if not token.revoked_at:
                    token.revoked_at = datetime.now(timezone.utc)

            self.db.commit()

    def get_user_by_id(self, user_id: int) -> AppUser | None:
        stmt = select(AppUser).where(AppUser.id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_me(self, user_id: int) -> UserResponse:
        user = self.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException()
        return self._build_user_response(user)

    def update_profile(self, user_id: int, data: UpdateProfileRequest) -> UserResponse:
        user = self.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException()

        if data.display_name is not None:
            user.display_name = data.display_name
        if data.locale_pref is not None:
            user.locale_pref = data.locale_pref
        if data.ui_lang is not None:
            user.ui_lang = data.ui_lang
        if data.audio_lang is not None:
            user.audio_lang = data.audio_lang
        if data.units is not None:
            user.units = data.units

        self.db.commit()
        self.db.refresh(user)

        return self._build_user_response(user)

    def delete_account(self, user_id: int) -> None:
        user = self.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException()

        self.db.delete(user)
        self.db.commit()

    def request_password_reset(self, email: str) -> str | None:
        """
        Request password reset. Returns the token for development purposes.
        In production, this should send an email instead.
        """
        email = email.lower()

        # Find email identity
        identity = self._find_identity_by_provider("email", email)
        if not identity:
            # Don't reveal if email exists
            return None

        # Create reset token
        raw_token, hashed_token, expires_at = create_password_reset_token()

        reset_token = PasswordResetToken(
            identity_id=identity.id,
            token_hash=hashed_token,
            expires_at=expires_at,
        )
        self.db.add(reset_token)
        self.db.commit()

        # TODO: Send email with reset link
        # For now, return the token (development mode only)
        return raw_token

    def confirm_password_reset(self, token: str, new_password: str) -> None:
        token_hash = hash_token(token)

        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
        reset_token = self.db.execute(stmt).scalar_one_or_none()

        if not reset_token:
            raise InvalidTokenException()

        # Update password
        identity = reset_token.identity
        identity.password_hash = hash_password(new_password)

        # Mark token as used
        reset_token.used_at = datetime.now(timezone.utc)

        # Increment token version to invalidate all sessions
        identity.user.token_version += 1

        # Revoke all refresh tokens
        for token in identity.user.refresh_tokens:
            if not token.revoked_at:
                token.revoked_at = datetime.now(timezone.utc)

        self.db.commit()
