"""SQL access for the inventory ledger.

`products.current_stock` is a cache of this ledger's running total. Every
function that changes stock does both writes on the same connection, so the two
can never disagree — callers pass in the connection from their transaction.
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection

from app.database import query_all, query_one

TRANSACTION_TYPES = (
    "SALE",
    "PURCHASE",
    "RETURN",
    "DAMAGE",
    "MANUAL_ADJUSTMENT",
    "OPENING_STOCK",
)

COLUMNS = """
    id, store_id, product_id, type, quantity_change, quantity_before,
    quantity_after, reference_type, reference_id, notes, created_by, created_at
"""


def apply_movement(
    conn: Connection,
    store_id: int,
    product_id: int,
    quantity_change: int,
    transaction_type: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
    notes: str | None = None,
    created_by: int | None = None,
    allow_negative: bool = False,
) -> dict[str, Any]:
    """Move stock and record why, atomically within the caller's transaction.

    `SELECT ... FOR UPDATE` serialises concurrent movements on the same product,
    so two simultaneous sales cannot both read the same "before" value and write
    a stock level that loses one of them.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT current_stock FROM products WHERE id = %s AND store_id = %s FOR UPDATE",
            (product_id, store_id),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(f"Product {product_id} not found in this store")

        before = int(row["current_stock"])
        after = before + quantity_change
        if after < 0 and not allow_negative:
            raise ValueError(
                f"Insufficient stock: {before} on hand, {abs(quantity_change)} requested"
            )
        after = max(after, 0)

        cur.execute(
            "UPDATE products SET current_stock = %s, updated_at = NOW() WHERE id = %s",
            (after, product_id),
        )
        cur.execute(
            f"""
            INSERT INTO inventory_transactions
                (store_id, product_id, type, quantity_change, quantity_before,
                 quantity_after, reference_type, reference_id, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {COLUMNS}
            """,
            (
                store_id, product_id, transaction_type, after - before, before,
                after, reference_type, reference_id, notes, created_by,
            ),
        )
        return cur.fetchone()


def list_movements(
    store_id: int,
    product_id: int | None = None,
    transaction_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses = ["t.store_id = %s"]
    params: list[Any] = [store_id]

    if product_id is not None:
        clauses.append("t.product_id = %s")
        params.append(product_id)
    if transaction_type:
        clauses.append("t.type = %s")
        params.append(transaction_type)

    params.extend([limit, offset])
    return query_all(
        f"""
        SELECT t.id, t.store_id, t.product_id, t.type, t.quantity_change,
               t.quantity_before, t.quantity_after, t.reference_type, t.reference_id,
               t.notes, t.created_by, t.created_at,
               p.name AS product_name, p.sku, u.full_name AS created_by_name
        FROM inventory_transactions t
        JOIN products p ON p.id = t.product_id
        LEFT JOIN users u ON u.id = t.created_by
        WHERE {' AND '.join(clauses)}
        ORDER BY t.created_at DESC, t.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )


def count_movements(
    store_id: int, product_id: int | None = None, transaction_type: str | None = None
) -> int:
    clauses = ["store_id = %s"]
    params: list[Any] = [store_id]
    if product_id is not None:
        clauses.append("product_id = %s")
        params.append(product_id)
    if transaction_type:
        clauses.append("type = %s")
        params.append(transaction_type)

    row = query_one(
        f"SELECT COUNT(*) AS total FROM inventory_transactions WHERE {' AND '.join(clauses)}",
        tuple(params),
    )
    return int(row["total"]) if row else 0


def stock_status_rows(store_id: int, limit: int = 500) -> list[dict[str, Any]]:
    """On-hand position per product, worst first — the /inventory table."""
    return query_all(
        """
        SELECT p.id AS product_id, p.sku, p.name, p.category, p.unit,
               p.current_stock, p.reorder_level, p.lead_time_days,
               p.cost_price, p.selling_price,
               p.current_stock * p.cost_price AS stock_value,
               CASE
                   WHEN p.current_stock <= 0 THEN 'OUT_OF_STOCK'
                   WHEN p.current_stock <= p.reorder_level THEN 'LOW'
                   ELSE 'OK'
               END AS stock_status,
               (SELECT MAX(t.created_at) FROM inventory_transactions t
                 WHERE t.product_id = p.id) AS last_movement_at
        FROM products p
        WHERE p.store_id = %s AND p.is_active = TRUE
        ORDER BY (p.current_stock <= 0) DESC,
                 (p.current_stock <= p.reorder_level) DESC,
                 p.name
        LIMIT %s
        """,
        (store_id, limit),
    )
