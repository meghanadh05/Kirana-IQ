"""SQL access for the products table.

These are plain functions over the psycopg helpers in app.database — the
project's stand-in for an ORM repository layer.
"""

from __future__ import annotations

from typing import Any

from app.database import execute, query_all, query_one

COLUMNS = "id, sku, name, category, unit_price, current_stock, reorder_level, lead_time_days"


def list_products(
    category: str | None = None,
    search: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return products, optionally filtered by category and name/SKU search."""
    clauses: list[str] = []
    params: list[Any] = []

    if category:
        clauses.append("category = %s")
        params.append(category)
    if search:
        clauses.append("(name ILIKE %s OR sku ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])

    return query_all(
        f"SELECT {COLUMNS} FROM products {where} ORDER BY sku LIMIT %s OFFSET %s",
        tuple(params),
    )


def get_product(product_id: int) -> dict[str, Any] | None:
    return query_one(f"SELECT {COLUMNS} FROM products WHERE id = %s", (product_id,))


def get_product_by_sku(sku: str) -> dict[str, Any] | None:
    return query_one(f"SELECT {COLUMNS} FROM products WHERE sku = %s", (sku,))


def create_product(data: dict[str, Any]) -> dict[str, Any]:
    return query_one(
        f"""
        INSERT INTO products
            (sku, name, category, unit_price, current_stock, reorder_level, lead_time_days)
        VALUES (%(sku)s, %(name)s, %(category)s, %(unit_price)s,
                %(current_stock)s, %(reorder_level)s, %(lead_time_days)s)
        RETURNING {COLUMNS}
        """,
        data,
    )


def list_categories() -> list[str]:
    rows = query_all("SELECT DISTINCT category FROM products ORDER BY category")
    return [row["category"] for row in rows]


def delete_product(product_id: int) -> int:
    """Delete a product and (via ON DELETE CASCADE) its sales."""
    return execute("DELETE FROM products WHERE id = %s", (product_id,))
