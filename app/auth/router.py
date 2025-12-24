from fastapi import APIRouter, status

from app.auth.dependencies import AuthServiceDep, CurrentUser, DeviceInfo
from app.auth.oauth.google import verify_google_token
from app.auth.schemas import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequestRequest,
    PasswordResetRequestResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest,
    auth_service: AuthServiceDep,
    device_info: DeviceInfo,
):
    """Register a new user with email and password."""
    return auth_service.register(data, device_info)


@router.post("/login", response_model=AuthResponse)
def login(
    data: LoginRequest,
    auth_service: AuthServiceDep,
    device_info: DeviceInfo,
):
    """Login with email and password."""
    return auth_service.login(data.email, data.password, device_info)


@router.post("/google", response_model=AuthResponse)
async def google_auth(
    data: GoogleAuthRequest,
    auth_service: AuthServiceDep,
    device_info: DeviceInfo,
):
    """Authenticate with Google OAuth."""
    google_data = await verify_google_token(data.id_token)

    return auth_service.google_auth(
        google_sub=google_data["sub"],
        email=google_data.get("email"),
        email_verified=google_data.get("email_verified", False),
        display_name=data.display_name or google_data.get("name"),
        locale_pref=data.locale_pref,
        ui_lang=data.ui_lang,
        audio_lang=data.audio_lang,
        units=data.units,
        device_info=device_info,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    data: RefreshTokenRequest,
    auth_service: AuthServiceDep,
    device_info: DeviceInfo,
):
    """Refresh access token using refresh token."""
    return auth_service.refresh_tokens(data.refresh_token, device_info)


@router.post("/password-reset/request", response_model=PasswordResetRequestResponse)
def request_password_reset(
    data: PasswordResetRequestRequest,
    auth_service: AuthServiceDep,
):
    """Request a password reset email."""
    reset_token = auth_service.request_password_reset(data.email)

    # In production, don't return the token - send it via email
    return PasswordResetRequestResponse(
        message="If the email exists, a password reset link has been sent.",
        reset_token=reset_token,  # Remove in production
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_password_reset(
    data: PasswordResetConfirmRequest,
    auth_service: AuthServiceDep,
):
    """Confirm password reset with token and new password."""
    auth_service.confirm_password_reset(data.token, data.new_password)
    return MessageResponse(message="Password has been reset successfully.")


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
):
    """Get current user profile."""
    return auth_service.get_me(current_user.id)


@router.patch("/me", response_model=UserResponse)
def update_profile(
    data: UpdateProfileRequest,
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
):
    """Update current user profile."""
    return auth_service.update_profile(current_user.id, data)


@router.post("/logout", response_model=MessageResponse)
def logout(
    data: LogoutRequest,
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
):
    """Logout from current device (revoke refresh token)."""
    auth_service.logout(data.refresh_token)
    return MessageResponse(message="Successfully logged out.")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
):
    """Logout from all devices."""
    auth_service.logout_all(current_user.id)
    return MessageResponse(message="Successfully logged out from all devices.")


@router.delete("/me", response_model=MessageResponse, status_code=status.HTTP_200_OK)
def delete_account(
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
):
    """Delete current user account."""
    auth_service.delete_account(current_user.id)
    return MessageResponse(message="Account has been deleted.")
