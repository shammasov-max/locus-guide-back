from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# ============ Request Schemas ============

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = None
    locale_pref: str | None = None
    ui_lang: str | None = None
    audio_lang: str | None = None
    units: Literal["metric", "imperial"] = "metric"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str
    display_name: str | None = None
    locale_pref: str | None = None
    ui_lang: str | None = None
    audio_lang: str | None = None
    units: Literal["metric", "imperial"] = "metric"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequestRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    locale_pref: str | None = None
    ui_lang: str | None = None
    audio_lang: str | None = None
    units: Literal["metric", "imperial"] | None = None


class LogoutRequest(BaseModel):
    refresh_token: str


# ============ Response Schemas ============

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: int
    email: str | None
    display_name: str | None
    locale_pref: str | None
    ui_lang: str | None
    audio_lang: str | None
    units: str
    created_at: datetime
    providers: list[str]  # List of connected providers: ['email', 'google']

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    message: str


class PasswordResetRequestResponse(BaseModel):
    message: str
    reset_token: str | None = None
