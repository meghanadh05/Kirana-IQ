"""SQL access for the sales table."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.database import query_all, query_one

COLUMNS = "id, product_id, quantity, sale_date, unit_price"


def list_sales(
    product_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Return a product's sales in chronological order."""
    clauses = ["product_id = %s"]
    params: list[Any] = [product_id]

    if start_date:
        clauses.append("sale_date >= %s")
        params.append(start_date)
    if end_date:
        clauses.append("sale_date <= %s")
        params.append(end_date)

    params.append(limit)
    return query_all(
        f"SELECT {COLUMNS} FROM sales WHERE {' AND '.join(clauses)} "
        f"ORDER BY sale_date LIMIT %s",
        tuple(params),
    )


def create_sale(data: dict[str, Any]) -> dict[str, Any]:
    return query_one(
        f"""
        INSERT INTO sales (product_id, quantity, sale_date, unit_price)
        VALUES (%(product_id)s, %(quantity)s, %(sale_date)s, %(unit_price)s)
        RETURNING {COLUMNS}
        """,
        data,
    )


def daily_history(product_id: int) -> list[dict[str, Any]]:
    """Total units sold per day for one product — the input to forecasting.

    Days with no sales are absent here; the feature pipeline reindexes onto a
    complete calendar and fills the gaps with zero.
    """
    return query_all(
        """
        SELECT sale_date, SUM(quantity) AS quantity
        FROM sales
        WHERE product_id = %s
        GROUP BY sale_date
        ORDER BY sale_date
        """,
        (product_id,),
    )


def sales_summary(product_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT COUNT(*) AS records,
               COALESCE(SUM(quantity), 0) AS total_units,
               MIN(sale_date) AS first_sale_date,
               MAX(sale_date) AS last_sale_date
        FROM sales
        WHERE product_id = %s
        """,
        (product_id,),
    )
