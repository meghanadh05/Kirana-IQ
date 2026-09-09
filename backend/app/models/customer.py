"""SQL access for customers.

Totals are derived from sales rather than stored on the customer row: a cached
`total_spent` that drifts from the invoices is worse than no number at all.
"""

from __future__ import annotations

from typing import Any

from app.database import execute, query_all, query_one
from psycopg import Connection

COLUMNS = "id, store_id, name, phone, email, notes, created_at, updated_at"

STATS = """
    COALESCE(agg.total_spent, 0)  AS total_spent,
    COALESCE(agg.purchase_count, 0) AS purchase_count,
    agg.last_purchase
"""

STATS_JOIN = """
    LEFT JOIN (
        SELECT customer_id,
               SUM(total)     AS total_spent,
               COUNT(*)       AS purchase_count,
               MAX(sale_date) AS last_purchase
        FROM sales
        WHERE store_id = %(store_id)s AND status = 'COMPLETED'
        GROUP BY customer_id
    ) agg ON agg.customer_id = c.id
"""


def list_customers(
    store_id: int, search: str | None = None, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    clauses = ["c.store_id = %(store_id)s"]
    params: dict[str, Any] = {"store_id": store_id, "limit": limit, "offset": offset}

    if search:
        clauses.append("(c.name ILIKE %(search)s OR c.phone ILIKE %(search)s "
                       "OR c.email ILIKE %(search)s)")
        params["search"] = f"%{search}%"

    return query_all(
        f"""
        SELECT c.id, c.store_id, c.name, c.phone, c.email, c.notes,
               c.created_at, c.updated_at, {STATS}
        FROM customers c
        {STATS_JOIN}
        WHERE {' AND '.join(clauses)}
        ORDER BY agg.last_purchase DESC NULLS LAST, c.name
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )


def count_customers(store_id: int, search: str | None = None) -> int:
    clauses = ["store_id = %(store_id)s"]
    params: dict[str, Any] = {"store_id": store_id}
    if search:
        clauses.append("(name ILIKE %(search)s OR phone ILIKE %(search)s OR email ILIKE %(search)s)")
        params["search"] = f"%{search}%"

    row = query_one(
        f"SELECT COUNT(*) AS total FROM customers WHERE {' AND '.join(clauses)}", params
    )
    return int(row["total"]) if row else 0


def get(customer_id: int, store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"""
        SELECT c.id, c.store_id, c.name, c.phone, c.email, c.notes,
               c.created_at, c.updated_at, {STATS}
        FROM customers c
        {STATS_JOIN}
        WHERE c.id = %(customer_id)s AND c.store_id = %(store_id)s
        """,
        {"customer_id": customer_id, "store_id": store_id},
    )


def get_by_phone(phone: str, store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"SELECT {COLUMNS} FROM customers WHERE phone = %s AND store_id = %s",
        (phone, store_id),
    )


def create(store_id: int, data: dict[str, Any]) -> dict[str, Any]:
    return query_one(
        f"""
        INSERT INTO customers (store_id, name, phone, email, notes)
        VALUES (%(store_id)s, %(name)s, %(phone)s, %(email)s, %(notes)s)
        RETURNING {COLUMNS}
        """,
        {**data, "store_id": store_id},
    )


def find_or_create(conn: Connection, store_id: int, name: str, phone: str | None) -> int | None:
    """Attach a POS sale to a customer record, creating one when the phone is new.

    Runs on the checkout's connection so a failed checkout does not leave a
    customer behind. A sale without a phone number stays anonymous — a name
    alone is not an identity worth deduplicating on.
    """
    if not phone:
        return None

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM customers WHERE store_id = %s AND phone = %s", (store_id, phone)
        )
        row = cur.fetchone()
        if row:
            return int(row["id"])

        cur.execute(
            "INSERT INTO customers (store_id, name, phone) VALUES (%s, %s, %s) RETURNING id",
            (store_id, name or "Walk-in customer", phone),
        )
        return int(cur.fetchone()["id"])


def update(customer_id: int, store_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    allowed = ("name", "phone", "email", "notes")
    fields = {key: value for key, value in data.items() if key in allowed}
    if not fields:
        return get(customer_id, store_id)

    assignments = ", ".join(f"{key} = %({key})s" for key in fields)
    query_one(
        f"UPDATE customers SET {assignments}, updated_at = NOW() "
        f"WHERE id = %(customer_id)s AND store_id = %(store_id)s RETURNING id",
        {**fields, "customer_id": customer_id, "store_id": store_id},
    )
    return get(customer_id, store_id)


def delete(customer_id: int, store_id: int) -> int:
    return execute(
        "DELETE FROM customers WHERE id = %s AND store_id = %s", (customer_id, store_id)
    )
