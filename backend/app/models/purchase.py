"""SQL access for purchase orders and their line items."""

from __future__ import annotations

from typing import Any

from psycopg import Connection

from app.database import query_all, query_one

COLUMNS = """
    id, store_id, po_number, supplier_id, status, subtotal, tax, total,
    expected_delivery, notes, created_by, created_at, updated_at, received_at
"""

ITEM_COLUMNS = """
    id, purchase_order_id, store_id, product_id, quantity, received_quantity,
    cost_price, tax_rate, line_total
"""

OPEN_STATUSES = ("DRAFT", "ORDERED", "PARTIALLY_RECEIVED")


def next_po_number(conn: Connection, store_id: int, prefix: str) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM purchase_orders WHERE store_id = %s", (store_id,))
        sequence = int(cur.fetchone()["total"]) + 1
    return f"{prefix}-{sequence:04d}"


def list_orders(
    store_id: int,
    status: str | None = None,
    supplier_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses = ["o.store_id = %s"]
    params: list[Any] = [store_id]

    if status:
        clauses.append("o.status = %s")
        params.append(status)
    if supplier_id is not None:
        clauses.append("o.supplier_id = %s")
        params.append(supplier_id)

    params.extend([limit, offset])
    return query_all(
        f"""
        SELECT o.id, o.store_id, o.po_number, o.supplier_id, o.status, o.subtotal,
               o.tax, o.total, o.expected_delivery, o.notes, o.created_by,
               o.created_at, o.updated_at, o.received_at,
               s.name AS supplier_name,
               COALESCE(i.item_count, 0) AS item_count,
               COALESCE(i.unit_count, 0) AS unit_count,
               COALESCE(i.received_count, 0) AS received_count
        FROM purchase_orders o
        LEFT JOIN suppliers s ON s.id = o.supplier_id
        LEFT JOIN (
            SELECT purchase_order_id, COUNT(*) AS item_count,
                   SUM(quantity) AS unit_count, SUM(received_quantity) AS received_count
            FROM purchase_order_items GROUP BY purchase_order_id
        ) i ON i.purchase_order_id = o.id
        WHERE {' AND '.join(clauses)}
        ORDER BY o.created_at DESC, o.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )


def count_orders(store_id: int, status: str | None = None, supplier_id: int | None = None) -> int:
    clauses = ["store_id = %s"]
    params: list[Any] = [store_id]
    if status:
        clauses.append("status = %s")
        params.append(status)
    if supplier_id is not None:
        clauses.append("supplier_id = %s")
        params.append(supplier_id)

    row = query_one(
        f"SELECT COUNT(*) AS total FROM purchase_orders WHERE {' AND '.join(clauses)}",
        tuple(params),
    )
    return int(row["total"]) if row else 0


def get(order_id: int, store_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT o.id, o.store_id, o.po_number, o.supplier_id, o.status, o.subtotal,
               o.tax, o.total, o.expected_delivery, o.notes, o.created_by,
               o.created_at, o.updated_at, o.received_at,
               s.name AS supplier_name, s.phone AS supplier_phone,
               s.contact_person AS supplier_contact
        FROM purchase_orders o
        LEFT JOIN suppliers s ON s.id = o.supplier_id
        WHERE o.id = %s AND o.store_id = %s
        """,
        (order_id, store_id),
    )


def get_items(order_id: int, store_id: int) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT i.id, i.purchase_order_id, i.store_id, i.product_id, i.quantity,
               i.received_quantity, i.cost_price, i.tax_rate, i.line_total,
               p.name AS product_name, p.sku, p.unit, p.current_stock
        FROM purchase_order_items i
        JOIN products p ON p.id = i.product_id
        WHERE i.purchase_order_id = %s AND i.store_id = %s
        ORDER BY i.id
        """,
        (order_id, store_id),
    )


def history_for_supplier(supplier_id: int, store_id: int, limit: int = 20) -> list[dict[str, Any]]:
    return query_all(
        f"SELECT {COLUMNS} FROM purchase_orders WHERE supplier_id = %s AND store_id = %s "
        f"ORDER BY created_at DESC LIMIT %s",
        (supplier_id, store_id, limit),
    )


def supplier_totals(supplier_id: int, store_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT COUNT(*)                                                     AS order_count,
               COUNT(*) FILTER (WHERE status IN ('ORDERED','PARTIALLY_RECEIVED')) AS open_orders,
               COALESCE(SUM(total) FILTER (WHERE status = 'RECEIVED'), 0)   AS total_purchased
        FROM purchase_orders
        WHERE supplier_id = %s AND store_id = %s
        """,
        (supplier_id, store_id),
    )
