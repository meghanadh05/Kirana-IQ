"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.deps import CurrentUser
from app.models import store as store_model
from app.models import user as user_model
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    PasswordChange,
    PasswordResetRequest,
    ProfileUpdate,
    RegisterRequest,
    SessionResponse,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> dict:
    """Create an account and sign in immediately."""
    return auth_service.register(
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
        phone=payload.phone,
    )


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest) -> dict:
    """Exchange credentials for an access token."""
    return auth_service.login(str(payload.email), payload.password)


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser) -> dict:
    """The signed-in user and the stores they can open."""
    return {"user": user, "stores": store_model.list_for_user(user["id"])}


@router.patch("/me", response_model=UserOut)
def update_profile(payload: ProfileUpdate, user: CurrentUser) -> dict:
    return user_model.update_profile(user["id"], payload.full_name, payload.phone)


@router.post("/change-password")
def change_password(payload: PasswordChange, user: CurrentUser) -> dict:
    auth_service.change_password(user["id"], payload.current_password, payload.new_password)
    return {"status": "updated"}


@router.post("/forgot-password")
def forgot_password(payload: PasswordResetRequest) -> dict:
    """Always reports success, so the endpoint cannot enumerate accounts."""
    auth_service.request_password_reset(str(payload.email))
    return {
        "status": "accepted",
        "message": "If an account exists for that address, reset instructions will be sent.",
    }
