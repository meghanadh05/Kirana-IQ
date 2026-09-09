"""Request/response models for authentication."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str | None = None
    is_active: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    # 72 bytes is bcrypt's hard limit; anything longer is silently truncated.
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=20)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class StoreSummary(BaseModel):
    id: int
    name: str
    role: str
    business_type: str
    currency: str
    is_demo: bool
    onboarding_completed: bool


class MeResponse(BaseModel):
    """The signed-in identity, without re-issuing a token."""

    user: UserOut
    stores: list[StoreSummary]


class SessionResponse(MeResponse):
    access_token: str
    token_type: str


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=20)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class PasswordResetRequest(BaseModel):
    email: EmailStr
