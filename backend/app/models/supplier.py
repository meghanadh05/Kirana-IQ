"""SQL access for suppliers."""

from __future__ import annotations

from typing import Any

from app.database import execute, query_all, query_one

COLUMNS = """
    id, store_id, name, contact_person, phone, email, address, gst_number,
    default_lead_time_days, notes, is_active, created_at, updated_at
"""


def list_suppliers(
    store_id: int, search: str | None = None, include_inactive: bool = False
) -> list[dict[str, Any]]:
    """Suppliers with the product and open-order counts the list view shows."""
    clauses = ["s.store_id = %(store_id)s"]
    params: dict[str, Any] = {"store_id": store_id}

    if not include_inactive:
        clauses.append("s.is_active = TRUE")
    if search:
        clauses.append("(s.name ILIKE %(search)s OR s.contact_person ILIKE %(search)s "
                       "OR s.phone ILIKE %(search)s)")
        params["search"] = f"%{search}%"

    return query_all(
        f"""
        SELECT s.id, s.store_id, s.name, s.contact_person, s.phone, s.email, s.address,
               s.gst_number, s.default_lead_time_days, s.notes, s.is_active,
               s.created_at, s.updated_at,
               COALESCE(p.product_count, 0)     AS product_count,
               COALESCE(o.open_orders, 0)       AS open_orders,
               COALESCE(o.total_purchased, 0)   AS total_purchased
        FROM suppliers s
        LEFT JOIN (
            SELECT supplier_id, COUNT(*) AS product_count
            FROM products WHERE store_id = %(store_id)s AND is_active GROUP BY supplier_id
        ) p ON p.supplier_id = s.id
        LEFT JOIN (
            SELECT supplier_id,
                   COUNT(*) FILTER (WHERE status IN ('ORDERED', 'PARTIALLY_RECEIVED')) AS open_orders,
                   SUM(total) FILTER (WHERE status = 'RECEIVED')                       AS total_purchased
            FROM purchase_orders WHERE store_id = %(store_id)s GROUP BY supplier_id
        ) o ON o.supplier_id = s.id
        WHERE {' AND '.join(clauses)}
        ORDER BY s.name
        """,
        params,
    )


def get(supplier_id: int, store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"SELECT {COLUMNS} FROM suppliers WHERE id = %s AND store_id = %s",
        (supplier_id, store_id),
    )


def create(store_id: int, data: dict[str, Any]) -> dict[str, Any]:
    return query_one(
        f"""
        INSERT INTO suppliers (store_id, name, contact_person, phone, email, address,
                               gst_number, default_lead_time_days, notes)
        VALUES (%(store_id)s, %(name)s, %(contact_person)s, %(phone)s, %(email)s,
                %(address)s, %(gst_number)s, %(default_lead_time_days)s, %(notes)s)
        RETURNING {COLUMNS}
        """,
        {**data, "store_id": store_id},
    )


def update(supplier_id: int, store_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    allowed = (
        "name", "contact_person", "phone", "email", "address", "gst_number",
        "default_lead_time_days", "notes", "is_active",
    )
    fields = {key: value for key, value in data.items() if key in allowed}
    if not fields:
        return get(supplier_id, store_id)

    assignments = ", ".join(f"{key} = %({key})s" for key in fields)
    return query_one(
        f"UPDATE suppliers SET {assignments}, updated_at = NOW() "
        f"WHERE id = %(supplier_id)s AND store_id = %(store_id)s RETURNING {COLUMNS}",
        {**fields, "supplier_id": supplier_id, "store_id": store_id},
    )


def archive(supplier_id: int, store_id: int) -> int:
    """Soft delete: purchase orders keep pointing at the supplier."""
    return execute(
        "UPDATE suppliers SET is_active = FALSE, updated_at = NOW() "
        "WHERE id = %s AND store_id = %s",
        (supplier_id, store_id),
    )


def supplied_products(supplier_id: int, store_id: int) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT id AS product_id, sku, name, category, current_stock, reorder_level,
               cost_price, selling_price, lead_time_days
        FROM products
        WHERE supplier_id = %s AND store_id = %s AND is_active = TRUE
        ORDER BY name
        """,
        (supplier_id, store_id),
    )
