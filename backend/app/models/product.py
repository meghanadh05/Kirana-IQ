"""SQL access for the products table.

These are plain functions over the psycopg helpers in app.database — the
project's stand-in for an ORM repository layer.

Every read takes a `store_id`. There is no unscoped variant on purpose: a query
without a tenant filter is a data leak waiting for its first bug.
"""

from __future__ import annotations

from typing import Any

from app.database import execute, query_all, query_one

# `selling_price` is also exposed as `unit_price`. The feature pipeline reads
# that key and the name is baked into the trained model's feature columns, so
# renaming the column did not rename what the model was trained on.
COLUMNS = (
    "id, store_id, sku, barcode, name, description, category, brand, unit, "
    "selling_price, selling_price AS unit_price, cost_price, tax_rate, "
    "current_stock, reorder_level, lead_time_days, supplier_id, is_active, "
    "created_at, updated_at"
)

SORTABLE = {
    "name": "name",
    "sku": "sku",
    "stock": "current_stock",
    "price": "selling_price",
    "created": "created_at",
    "category": "category",
}


def _columns(alias: str) -> str:
    """COLUMNS qualified with a table alias, for queries that join."""
    parts = []
    for part in COLUMNS.split(","):
        part = part.strip()
        if " AS " in part:
            source, target = part.split(" AS ")
            parts.append(f"{alias}.{source.strip()} AS {target.strip()}")
        else:
            parts.append(f"{alias}.{part}")
    return ", ".join(parts)


def list_products(
    store_id: int,
    category: str | None = None,
    search: str | None = None,
    brand: str | None = None,
    supplier_id: int | None = None,
    stock_status: str | None = None,
    is_active: bool | None = True,
    sort: str = "name",
    direction: str = "asc",
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Filtered, sorted page of a store's catalogue."""
    clauses = ["store_id = %s"]
    params: list[Any] = [store_id]

    if category:
        clauses.append("category = %s")
        params.append(category)
    if brand:
        clauses.append("brand = %s")
        params.append(brand)
    if supplier_id is not None:
        clauses.append("supplier_id = %s")
        params.append(supplier_id)
    if is_active is not None:
        clauses.append("is_active = %s")
        params.append(is_active)
    if search:
        # Barcode is matched exactly as well as by prefix, so a scanner's exact
        # code wins even when it is a substring of another product's SKU.
        clauses.append("(name ILIKE %s OR sku ILIKE %s OR barcode = %s OR brand ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%", search, f"%{search}%"])

    if stock_status == "out":
        clauses.append("current_stock <= 0")
    elif stock_status == "low":
        clauses.append("current_stock > 0 AND current_stock <= reorder_level")
    elif stock_status == "in":
        clauses.append("current_stock > reorder_level")

    order_column = SORTABLE.get(sort, "name")
    order_direction = "DESC" if str(direction).lower() == "desc" else "ASC"

    params.extend([limit, offset])
    return query_all(
        f"SELECT {COLUMNS} FROM products WHERE {' AND '.join(clauses)} "
        f"ORDER BY {order_column} {order_direction}, id LIMIT %s OFFSET %s",
        tuple(params),
    )


def count_products(
    store_id: int,
    category: str | None = None,
    search: str | None = None,
    brand: str | None = None,
    supplier_id: int | None = None,
    stock_status: str | None = None,
    is_active: bool | None = True,
) -> int:
    """Total matching rows, for pagination."""
    clauses = ["store_id = %s"]
    params: list[Any] = [store_id]

    if category:
        clauses.append("category = %s")
        params.append(category)
    if brand:
        clauses.append("brand = %s")
        params.append(brand)
    if supplier_id is not None:
        clauses.append("supplier_id = %s")
        params.append(supplier_id)
    if is_active is not None:
        clauses.append("is_active = %s")
        params.append(is_active)
    if search:
        clauses.append("(name ILIKE %s OR sku ILIKE %s OR barcode = %s OR brand ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%", search, f"%{search}%"])
    if stock_status == "out":
        clauses.append("current_stock <= 0")
    elif stock_status == "low":
        clauses.append("current_stock > 0 AND current_stock <= reorder_level")
    elif stock_status == "in":
        clauses.append("current_stock > reorder_level")

    row = query_one(
        f"SELECT COUNT(*) AS total FROM products WHERE {' AND '.join(clauses)}",
        tuple(params),
    )
    return int(row["total"]) if row else 0


def get_product(product_id: int, store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"SELECT {COLUMNS} FROM products WHERE id = %s AND store_id = %s",
        (product_id, store_id),
    )


def get_product_by_sku(sku: str, store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"SELECT {COLUMNS} FROM products WHERE sku = %s AND store_id = %s", (sku, store_id)
    )


def get_product_by_barcode(barcode: str, store_id: int) -> dict[str, Any] | None:
    """Exact barcode lookup — the POS scan path."""
    return query_one(
        f"SELECT {COLUMNS} FROM products WHERE barcode = %s AND store_id = %s",
        (barcode, store_id),
    )


def create_product(data: dict[str, Any]) -> dict[str, Any]:
    return query_one(
        f"""
        INSERT INTO products
            (store_id, sku, barcode, name, description, category, brand, unit,
             selling_price, cost_price, tax_rate, current_stock, reorder_level,
             lead_time_days, supplier_id, is_active)
        VALUES (%(store_id)s, %(sku)s, %(barcode)s, %(name)s, %(description)s,
                %(category)s, %(brand)s, %(unit)s, %(selling_price)s, %(cost_price)s,
                %(tax_rate)s, %(current_stock)s, %(reorder_level)s, %(lead_time_days)s,
                %(supplier_id)s, %(is_active)s)
        RETURNING {COLUMNS}
        """,
        data,
    )


UPDATABLE = (
    "sku", "barcode", "name", "description", "category", "brand", "unit",
    "selling_price", "cost_price", "tax_rate", "reorder_level", "lead_time_days",
    "supplier_id", "is_active",
)


def update_product(product_id: int, store_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """Patch a product. `current_stock` is deliberately not updatable here —
    stock only moves through the inventory ledger."""
    fields = {key: value for key, value in data.items() if key in UPDATABLE}
    if not fields:
        return get_product(product_id, store_id)

    assignments = ", ".join(f"{key} = %({key})s" for key in fields)
    return query_one(
        f"UPDATE products SET {assignments}, updated_at = NOW() "
        f"WHERE id = %(product_id)s AND store_id = %(store_id)s RETURNING {COLUMNS}",
        {**fields, "product_id": product_id, "store_id": store_id},
    )


def archive_product(product_id: int, store_id: int) -> int:
    """Soft delete. Sale items reference products, so rows are never removed."""
    return execute(
        "UPDATE products SET is_active = FALSE, updated_at = NOW() "
        "WHERE id = %s AND store_id = %s",
        (product_id, store_id),
    )


def list_categories(store_id: int) -> list[str]:
    rows = query_all(
        "SELECT DISTINCT category FROM products WHERE store_id = %s ORDER BY category",
        (store_id,),
    )
    return [row["category"] for row in rows]


def list_brands(store_id: int) -> list[str]:
    rows = query_all(
        "SELECT DISTINCT brand FROM products WHERE store_id = %s AND brand IS NOT NULL "
        "ORDER BY brand",
        (store_id,),
    )
    return [row["brand"] for row in rows]


def catalogue_stats(store_id: int) -> dict[str, Any]:
    """Counts and valuation for the products page header and dashboard cards."""
    return query_one(
        """
        SELECT COUNT(*)                                                   AS total,
               COUNT(*) FILTER (WHERE current_stock <= 0)                 AS out_of_stock,
               COUNT(*) FILTER (WHERE current_stock > 0
                                  AND current_stock <= reorder_level)     AS low_stock,
               COALESCE(SUM(current_stock * cost_price), 0)               AS inventory_cost_value,
               COALESCE(SUM(current_stock * selling_price), 0)            AS inventory_retail_value
        FROM products
        WHERE store_id = %s AND is_active = TRUE
        """,
        (store_id,),
    )
