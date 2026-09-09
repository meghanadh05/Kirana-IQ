"""SQL access for stores, memberships and per-store settings."""

from __future__ import annotations

from typing import Any

from app.database import execute, query_all, query_one

COLUMNS = """
    id, name, owner_name, phone, email, address, city, state, pin_code,
    gst_number, currency, business_type, is_demo, onboarding_step,
    onboarding_completed, created_by, created_at, updated_at
"""

SETTINGS_COLUMNS = """
    store_id, low_stock_threshold, default_tax_rate, default_lead_time_days,
    invoice_prefix, purchase_order_prefix, financial_year_start_month, timezone,
    critical_cover_days, medium_cover_buffer_days, overstock_cover_days,
    safety_days, service_level_z, updated_at
"""


def _qualified(alias: str) -> str:
    """COLUMNS prefixed with a table alias, for queries that join."""
    names = [part.strip() for part in COLUMNS.split(",")]
    return ", ".join(f"{alias}.{name}" for name in names if name)


def get(store_id: int) -> dict[str, Any] | None:
    return query_one(f"SELECT {COLUMNS} FROM stores WHERE id = %s", (store_id,))


def list_for_user(user_id: int) -> list[dict[str, Any]]:
    """Every store the user belongs to, with their role in each."""
    return query_all(
        f"""
        SELECT {_qualified("s")}, m.role
        FROM stores s
        JOIN store_members m ON m.store_id = s.id
        WHERE m.user_id = %s
        ORDER BY s.created_at
        """,
        (user_id,),
    )


def create(data: dict[str, Any], created_by: int) -> dict[str, Any]:
    return query_one(
        f"""
        INSERT INTO stores (name, owner_name, phone, email, address, city, state,
                            pin_code, gst_number, currency, business_type, created_by)
        VALUES (%(name)s, %(owner_name)s, %(phone)s, %(email)s, %(address)s, %(city)s,
                %(state)s, %(pin_code)s, %(gst_number)s, %(currency)s,
                %(business_type)s, %(created_by)s)
        RETURNING {COLUMNS}
        """,
        {**data, "created_by": created_by},
    )


def update(store_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """Patch the named columns only; unknown keys are ignored by the caller."""
    allowed = (
        "name", "owner_name", "phone", "email", "address", "city", "state",
        "pin_code", "gst_number", "currency", "business_type",
        "onboarding_step", "onboarding_completed",
    )
    fields = {key: value for key, value in data.items() if key in allowed}
    if not fields:
        return get(store_id)

    assignments = ", ".join(f"{key} = %({key})s" for key in fields)
    return query_one(
        f"UPDATE stores SET {assignments}, updated_at = NOW() WHERE id = %(store_id)s "
        f"RETURNING {COLUMNS}",
        {**fields, "store_id": store_id},
    )


# --- Membership -----------------------------------------------------------


def add_member(store_id: int, user_id: int, role: str) -> dict[str, Any]:
    return query_one(
        """
        INSERT INTO store_members (store_id, user_id, role)
        VALUES (%s, %s, %s)
        ON CONFLICT (store_id, user_id) DO UPDATE SET role = EXCLUDED.role
        RETURNING id, store_id, user_id, role, created_at
        """,
        (store_id, user_id, role),
    )


def get_membership(store_id: int, user_id: int) -> dict[str, Any] | None:
    """The authorisation primitive: no row means no access to this store."""
    return query_one(
        "SELECT id, store_id, user_id, role, created_at FROM store_members "
        "WHERE store_id = %s AND user_id = %s",
        (store_id, user_id),
    )


def list_members(store_id: int) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT m.id, m.store_id, m.user_id, m.role, m.created_at,
               u.email, u.full_name, u.phone
        FROM store_members m
        JOIN users u ON u.id = m.user_id
        WHERE m.store_id = %s
        ORDER BY m.created_at
        """,
        (store_id,),
    )


def remove_member(store_id: int, user_id: int) -> int:
    return execute(
        "DELETE FROM store_members WHERE store_id = %s AND user_id = %s",
        (store_id, user_id),
    )


def count_owners(store_id: int) -> int:
    row = query_one(
        "SELECT COUNT(*) AS total FROM store_members WHERE store_id = %s AND role = 'OWNER'",
        (store_id,),
    )
    return int(row["total"]) if row else 0


# --- Settings -------------------------------------------------------------


def get_settings_row(store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"SELECT {SETTINGS_COLUMNS} FROM store_settings WHERE store_id = %s", (store_id,)
    )


def create_settings(store_id: int, defaults: dict[str, Any]) -> dict[str, Any]:
    """Seed a store's policy from the global environment defaults."""
    return query_one(
        f"""
        INSERT INTO store_settings (store_id, critical_cover_days, medium_cover_buffer_days,
                                    overstock_cover_days, safety_days, service_level_z)
        VALUES (%(store_id)s, %(critical_cover_days)s, %(medium_cover_buffer_days)s,
                %(overstock_cover_days)s, %(safety_days)s, %(service_level_z)s)
        ON CONFLICT (store_id) DO NOTHING
        RETURNING {SETTINGS_COLUMNS}
        """,
        {**defaults, "store_id": store_id},
    ) or get_settings_row(store_id)


def update_settings(store_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    allowed = (
        "low_stock_threshold", "default_tax_rate", "default_lead_time_days",
        "invoice_prefix", "purchase_order_prefix", "financial_year_start_month",
        "timezone", "critical_cover_days", "medium_cover_buffer_days",
        "overstock_cover_days", "safety_days", "service_level_z",
    )
    fields = {key: value for key, value in data.items() if key in allowed}
    if not fields:
        return get_settings_row(store_id)

    assignments = ", ".join(f"{key} = %({key})s" for key in fields)
    return query_one(
        f"UPDATE store_settings SET {assignments}, updated_at = NOW() "
        f"WHERE store_id = %(store_id)s RETURNING {SETTINGS_COLUMNS}",
        {**fields, "store_id": store_id},
    )
