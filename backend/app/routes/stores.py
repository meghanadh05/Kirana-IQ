"""Store, onboarding, settings and team endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.deps import CurrentUser, OwnerStore, PathManagerStore, PathOwnerStore, PathStore, Store
from app.models import store as store_model
from app.schemas.store import (
    MemberCreate,
    MemberOut,
    MemberRoleUpdate,
    OnboardingStep,
    StoreCreate,
    StoreOut,
    StoreSettingsOut,
    StoreSettingsUpdate,
    StoreUpdate,
)
from app.services import store_service

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("", response_model=list[StoreOut])
def list_stores(user: CurrentUser) -> list[dict]:
    """Stores the signed-in user is a member of."""
    return store_model.list_for_user(user["id"])


@router.post("", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
def create_store(payload: StoreCreate, user: CurrentUser) -> dict:
    """Create a store. The creator becomes its owner."""
    data = payload.model_dump()
    data["email"] = str(data["email"]) if data["email"] else None
    # model_dump() supplies an explicit None, so setdefault would not fire.
    data["owner_name"] = data.get("owner_name") or user["full_name"]
    return store_service.create_store(data, user["id"])


@router.get("/current", response_model=StoreOut)
def get_current_store(context: Store) -> dict:
    """The active store, resolved from the X-Store-Id header."""
    return {**context.store, "role": context.role}


@router.get("/current/settings", response_model=StoreSettingsOut)
def get_current_settings(context: Store) -> dict:
    return store_service.get_settings_for_store(context.store_id)


@router.patch("/current/settings", response_model=StoreSettingsOut)
def update_current_settings(payload: StoreSettingsUpdate, context: OwnerStore) -> dict:
    return store_service.update_store_settings(
        context.store_id, payload.model_dump(exclude_unset=True, exclude_none=True)
    )


@router.get("/{store_id}", response_model=StoreOut)
def get_store(context: PathStore) -> dict:
    return {**context.store, "role": context.role}


@router.patch("/{store_id}", response_model=StoreOut)
def update_store(payload: StoreUpdate, context: PathManagerStore) -> dict:
    """Update store details. Managers and owners only."""
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "email" in data:
        data["email"] = str(data["email"])
    return {**store_service.update_store(context.store_id, data), "role": context.role}


@router.post("/{store_id}/onboarding", response_model=StoreOut)
def set_onboarding_step(payload: OnboardingStep, context: PathManagerStore) -> dict:
    """Record onboarding wizard progress."""
    return {**store_service.advance_onboarding(context.store_id, payload.step), "role": context.role}


@router.get("/{store_id}/members", response_model=list[MemberOut])
def list_members(context: PathStore) -> list[dict]:
    return store_service.list_members(context.store_id)


@router.post("/{store_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(payload: MemberCreate, context: PathOwnerStore) -> dict:
    """Invite an existing account into this store. Owners only."""
    return store_service.add_member(context.store_id, str(payload.email), payload.role)


@router.patch("/{store_id}/members/{user_id}", response_model=MemberOut)
def update_member_role(user_id: int, payload: MemberRoleUpdate, context: PathOwnerStore) -> dict:
    """Change a member's role. Owners only."""
    return store_service.update_member_role(context.store_id, user_id, payload.role)


@router.delete("/{store_id}/members/{user_id}")
def remove_member(user_id: int, context: PathOwnerStore) -> dict:
    """Revoke a member's access. Owners only."""
    store_service.remove_member(context.store_id, user_id)
    return {"status": "removed"}
