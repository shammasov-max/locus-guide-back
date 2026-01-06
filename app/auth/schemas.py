from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Request schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    display_name: str | None = Field(None, max_length=100)
    units: str = Field("metric", pattern="^(metric|imperial)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


class LogoutRequest(BaseModel):
    refresh_token: str


class UpdateMeRequest(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    units: str | None = Field(None, pattern="^(metric|imperial)$")
    locale_pref: str | None = Field(None, max_length=10)
    ui_lang: str | None = Field(None, max_length=10)
    audio_lang: str | None = Field(None, max_length=10)
    character: dict[str, Any] | None = None


# Response schemas
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None
    role: str
    locale_pref: str | None
    ui_lang: str | None
    audio_lang: str | None
    character: dict[str, Any] | None
    units: str
    created_at: datetime
    providers: list[str] = []


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    message: str
