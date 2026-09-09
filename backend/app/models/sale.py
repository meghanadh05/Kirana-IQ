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
    """Total units and average price per day for one product.

    This is the input to the forecasting pipeline. Days with no sales are absent
    here; the feature pipeline reindexes onto a complete calendar and fills the
    gaps with zero. The average price drives the promotion flag.
    """
    return query_all(
        """
        SELECT sale_date,
               SUM(quantity) AS quantity,
               AVG(unit_price) AS avg_price
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


def latest_sale_date() -> Any:
    """Most recent sale date in the table.

    Analytics windows are anchored to this rather than to today's date: the
    sample dataset ends at a fixed point, and anchoring to `CURRENT_DATE` would
    silently return empty results the day after it was generated.
    """
    row = query_one("SELECT MAX(sale_date) AS last_day FROM sales")
    return row["last_day"] if row else None


def recent_totals(days: int = 30) -> list[dict[str, Any]]:
    """Units and revenue per product over the trailing window."""
    return query_all(
        """
        WITH anchor AS (SELECT MAX(sale_date) AS last_day FROM sales)
        SELECT p.id            AS product_id,
               p.sku,
               p.name,
               p.category,
               p.current_stock,
               COALESCE(SUM(s.quantity), 0)                  AS total_units,
               COALESCE(SUM(s.quantity * s.unit_price), 0)   AS total_revenue
        FROM products p
        LEFT JOIN sales s
               ON s.product_id = p.id
              AND s.sale_date > (SELECT last_day FROM anchor) - %s::int
        GROUP BY p.id, p.sku, p.name, p.category, p.current_stock
        ORDER BY total_units DESC
        """,
        (days,),
    )


def category_totals(days: int = 30) -> list[dict[str, Any]]:
    """Units per category for the trailing window and the window before it."""
    return query_all(
        """
        WITH anchor AS (SELECT MAX(sale_date) AS last_day FROM sales)
        SELECT p.category,
               COALESCE(SUM(s.quantity) FILTER (
                   WHERE s.sale_date > (SELECT last_day FROM anchor) - %(days)s::int
               ), 0) AS current_units,
               COALESCE(SUM(s.quantity) FILTER (
                   WHERE s.sale_date > (SELECT last_day FROM anchor) - (2 * %(days)s)::int
                     AND s.sale_date <= (SELECT last_day FROM anchor) - %(days)s::int
               ), 0) AS previous_units
        FROM products p
        LEFT JOIN sales s ON s.product_id = p.id
        GROUP BY p.category
        ORDER BY current_units DESC
        """,
        {"days": days},
    )


def daily_totals(days: int = 30) -> list[dict[str, Any]]:
    """Total units sold per day across the whole catalogue."""
    return query_all(
        """
        WITH anchor AS (SELECT MAX(sale_date) AS last_day FROM sales)
        SELECT sale_date, SUM(quantity) AS quantity
        FROM sales
        WHERE sale_date > (SELECT last_day FROM anchor) - %s::int
        GROUP BY sale_date
        ORDER BY sale_date
        """,
        (days,),
    )
