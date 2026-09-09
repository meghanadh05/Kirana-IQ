"""SQL access for per-store product categories."""

from __future__ import annotations

from typing import Any

from app.database import execute, query_all, query_one

COLUMNS = "id, store_id, name, description, created_at"


def list_categories(store_id: int) -> list[dict[str, Any]]:
    """Categories with a live product count, so empty ones are obvious."""
    return query_all(
        f"""
        SELECT c.id, c.store_id, c.name, c.description, c.created_at,
               COUNT(p.id) FILTER (WHERE p.is_active) AS product_count
        FROM categories c
        LEFT JOIN products p ON p.store_id = c.store_id AND p.category = c.name
        WHERE c.store_id = %s
        GROUP BY c.id
        ORDER BY c.name
        """,
        (store_id,),
    )


def get(category_id: int, store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"SELECT {COLUMNS} FROM categories WHERE id = %s AND store_id = %s",
        (category_id, store_id),
    )


def create(store_id: int, name: str, description: str | None = None) -> dict[str, Any]:
    return query_one(
        f"INSERT INTO categories (store_id, name, description) VALUES (%s, %s, %s) "
        f"RETURNING {COLUMNS}",
        (store_id, name, description),
    )


def ensure(store_id: int, name: str) -> None:
    """Register a category seen on a product. Import and product creation use it."""
    execute(
        "INSERT INTO categories (store_id, name) VALUES (%s, %s) "
        "ON CONFLICT (store_id, name) DO NOTHING",
        (store_id, name),
    )


def rename(category_id: int, store_id: int, name: str, description: str | None) -> dict[str, Any] | None:
    return query_one(
        f"UPDATE categories SET name = %s, description = %s "
        f"WHERE id = %s AND store_id = %s RETURNING {COLUMNS}",
        (name, description, category_id, store_id),
    )


def delete(category_id: int, store_id: int) -> int:
    return execute(
        "DELETE FROM categories WHERE id = %s AND store_id = %s", (category_id, store_id)
    )


def product_count(store_id: int, name: str) -> int:
    row = query_one(
        "SELECT COUNT(*) AS total FROM products WHERE store_id = %s AND category = %s",
        (store_id, name),
    )
    return int(row["total"]) if row else 0
