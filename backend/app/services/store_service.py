"""Store creation, onboarding, settings and team membership.

Creating a store is the only place a user grants themselves access: the creator
becomes its OWNER, and every later member is added by an existing owner.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.database import transaction
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import store as store_model
from app.models import user as user_model

BUSINESS_TYPES = (
    "KIRANA",
    "GROCERY",
    "MINI_SUPERMARKET",
    "PHARMACY",
    "CONVENIENCE_STORE",
    "OTHER",
)

ONBOARDING_STEPS = 4


def create_store(data: dict[str, Any], user_id: int) -> dict[str, Any]:
    """Create a store, its owner membership and its settings as one unit."""
    if data.get("business_type") and data["business_type"] not in BUSINESS_TYPES:
        raise ValidationError(f"business_type must be one of {list(BUSINESS_TYPES)}")

    settings = get_settings()
    defaults = {
        "critical_cover_days": settings.critical_cover_days,
        "medium_cover_buffer_days": settings.medium_cover_buffer_days,
        "overstock_cover_days": settings.overstock_cover_days,
        "safety_days": settings.safety_days,
        "service_level_z": settings.service_level_z,
    }

    # One transaction: a store with no owner would be unreachable forever.
    with transaction() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stores (name, owner_name, phone, email, address, city, state,
                                pin_code, gst_number, currency, business_type, created_by)
            VALUES (%(name)s, %(owner_name)s, %(phone)s, %(email)s, %(address)s, %(city)s,
                    %(state)s, %(pin_code)s, %(gst_number)s, %(currency)s,
                    %(business_type)s, %(created_by)s)
            RETURNING id
            """,
            {**data, "created_by": user_id},
        )
        store_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO store_members (store_id, user_id, role) VALUES (%s, %s, 'OWNER')",
            (store_id, user_id),
        )
        cur.execute(
            """
            INSERT INTO store_settings (store_id, critical_cover_days, medium_cover_buffer_days,
                                        overstock_cover_days, safety_days, service_level_z)
            VALUES (%(store_id)s, %(critical_cover_days)s, %(medium_cover_buffer_days)s,
                    %(overstock_cover_days)s, %(safety_days)s, %(service_level_z)s)
            """,
            {**defaults, "store_id": store_id},
        )

    return {**store_model.get(store_id), "role": "OWNER"}


def update_store(store_id: int, data: dict[str, Any]) -> dict[str, Any]:
    if data.get("business_type") and data["business_type"] not in BUSINESS_TYPES:
        raise ValidationError(f"business_type must be one of {list(BUSINESS_TYPES)}")
    store = store_model.update(store_id, data)
    if store is None:
        raise NotFoundError(f"Store {store_id} not found")
    return store


def advance_onboarding(store_id: int, step: int) -> dict[str, Any]:
    """Record wizard progress; the final step marks onboarding complete."""
    if step < 1 or step > ONBOARDING_STEPS:
        raise ValidationError(f"step must be between 1 and {ONBOARDING_STEPS}")
    return store_model.update(
        store_id,
        {"onboarding_step": step, "onboarding_completed": step >= ONBOARDING_STEPS},
    )


def get_settings_for_store(store_id: int) -> dict[str, Any]:
    """Store policy, creating the row from global defaults if it is missing."""
    row = store_model.get_settings_row(store_id)
    if row is not None:
        return row

    settings = get_settings()
    return store_model.create_settings(
        store_id,
        {
            "critical_cover_days": settings.critical_cover_days,
            "medium_cover_buffer_days": settings.medium_cover_buffer_days,
            "overstock_cover_days": settings.overstock_cover_days,
            "safety_days": settings.safety_days,
            "service_level_z": settings.service_level_z,
        },
    )


def update_store_settings(store_id: int, data: dict[str, Any]) -> dict[str, Any]:
    get_settings_for_store(store_id)  # ensure the row exists
    return store_model.update_settings(store_id, data)


# --- Team -----------------------------------------------------------------


def list_members(store_id: int) -> list[dict[str, Any]]:
    return store_model.list_members(store_id)


def add_member(store_id: int, email: str, role: str) -> dict[str, Any]:
    """Grant an existing account access to this store."""
    if role not in ("OWNER", "MANAGER", "CASHIER"):
        raise ValidationError("role must be OWNER, MANAGER or CASHIER")

    user = user_model.get_by_email(email.strip().lower())
    if user is None:
        raise NotFoundError(
            "No account with that email. Ask them to sign up first, then invite them."
        )
    if store_model.get_membership(store_id, user["id"]) is not None:
        raise ConflictError("That user is already a member of this store")

    store_model.add_member(store_id, user["id"], role)
    return next(m for m in store_model.list_members(store_id) if m["user_id"] == user["id"])


def update_member_role(store_id: int, user_id: int, role: str) -> dict[str, Any]:
    if role not in ("OWNER", "MANAGER", "CASHIER"):
        raise ValidationError("role must be OWNER, MANAGER or CASHIER")

    membership = store_model.get_membership(store_id, user_id)
    if membership is None:
        raise NotFoundError("That user is not a member of this store")
    # Demoting the last owner would leave the store with nobody who can manage it.
    if membership["role"] == "OWNER" and role != "OWNER" and store_model.count_owners(store_id) <= 1:
        raise ConflictError("A store must keep at least one owner")

    store_model.add_member(store_id, user_id, role)
    return next(m for m in store_model.list_members(store_id) if m["user_id"] == user_id)


def remove_member(store_id: int, user_id: int) -> None:
    membership = store_model.get_membership(store_id, user_id)
    if membership is None:
        raise NotFoundError("That user is not a member of this store")
    if membership["role"] == "OWNER" and store_model.count_owners(store_id) <= 1:
        raise ConflictError("A store must keep at least one owner")
    store_model.remove_member(store_id, user_id)
