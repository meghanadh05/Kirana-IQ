"""SQL access for sales, sale items and the demand aggregates built from them.

The forecasting pipeline consumes `daily_history`, which is now derived from
POS line items rather than a flat sales table. That is the whole point of the
integration: every checkout feeds the model.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from psycopg import Connection

from app.database import query_all, query_one

SALE_COLUMNS = """
    id, store_id, invoice_number, customer_id, customer_name, customer_phone,
    subtotal, discount, tax, total, cost_total, payment_method, amount_received,
    change_due, status, notes, sale_date, created_by, created_at
"""

ITEM_COLUMNS = """
    id, sale_id, store_id, product_id, product_name, sku, quantity, unit_price,
    cost_price, discount, tax_rate, tax_amount, line_total, sale_date
"""


# --------------------------------------------------------------------------
# Demand history (the forecasting input)
# --------------------------------------------------------------------------


def daily_history(product_id: int, store_id: int) -> list[dict[str, Any]]:
    """Total units and average price per day for one product.

    Days with no sales are absent here; the feature pipeline reindexes onto a
    complete calendar and fills the gaps with zero. The average price drives the
    promotion flag. Cancelled and returned invoices are excluded — they did not
    represent real demand.
    """
    return query_all(
        """
        SELECT i.sale_date,
               SUM(i.quantity)   AS quantity,
               AVG(i.unit_price) AS avg_price
        FROM sale_items i
        JOIN sales s ON s.id = i.sale_id
        WHERE i.product_id = %s AND i.store_id = %s AND s.status = 'COMPLETED'
        GROUP BY i.sale_date
        ORDER BY i.sale_date
        """,
        (product_id, store_id),
    )


def sales_summary(product_id: int, store_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT COUNT(*)                       AS records,
               COALESCE(SUM(i.quantity), 0)   AS total_units,
               MIN(i.sale_date)               AS first_sale_date,
               MAX(i.sale_date)               AS last_sale_date
        FROM sale_items i
        JOIN sales s ON s.id = i.sale_id
        WHERE i.product_id = %s AND i.store_id = %s AND s.status = 'COMPLETED'
        """,
        (product_id, store_id),
    )


def latest_sale_date(store_id: int) -> Any:
    """Most recent sale date in this store.

    Analytics windows are anchored to this rather than to today's date: a demo
    dataset ends at a fixed point, and anchoring to `CURRENT_DATE` would
    silently return empty results the day after it was generated.
    """
    row = query_one(
        "SELECT MAX(sale_date) AS last_day FROM sale_items WHERE store_id = %s", (store_id,)
    )
    return row["last_day"] if row else None


def recent_totals(store_id: int, days: int = 30) -> list[dict[str, Any]]:
    """Units, revenue and cost per product over the trailing window."""
    return query_all(
        """
        WITH anchor AS (
            SELECT COALESCE(MAX(sale_date), CURRENT_DATE) AS last_day
            FROM sale_items WHERE store_id = %(store_id)s
        )
        SELECT p.id            AS product_id,
               p.sku,
               p.name,
               p.category,
               p.current_stock,
               p.cost_price,
               p.selling_price,
               COALESCE(SUM(i.quantity), 0)                    AS total_units,
               COALESCE(SUM(i.line_total), 0)                  AS total_revenue,
               COALESCE(SUM(i.quantity * i.cost_price), 0)     AS total_cost
        FROM products p
        LEFT JOIN sale_items i
               ON i.product_id = p.id
              AND i.sale_date > (SELECT last_day FROM anchor) - %(days)s::int
        LEFT JOIN sales s ON s.id = i.sale_id AND s.status = 'COMPLETED'
        WHERE p.store_id = %(store_id)s AND p.is_active = TRUE
        GROUP BY p.id, p.sku, p.name, p.category, p.current_stock, p.cost_price, p.selling_price
        ORDER BY total_units DESC
        """,
        {"store_id": store_id, "days": days},
    )


def category_totals(store_id: int, days: int = 30) -> list[dict[str, Any]]:
    """Units and revenue per category for the window and the window before it."""
    return query_all(
        """
        WITH anchor AS (
            SELECT COALESCE(MAX(sale_date), CURRENT_DATE) AS last_day
            FROM sale_items WHERE store_id = %(store_id)s
        )
        SELECT p.category,
               COALESCE(SUM(i.quantity) FILTER (
                   WHERE i.sale_date > (SELECT last_day FROM anchor) - %(days)s::int
               ), 0) AS current_units,
               COALESCE(SUM(i.line_total) FILTER (
                   WHERE i.sale_date > (SELECT last_day FROM anchor) - %(days)s::int
               ), 0) AS current_revenue,
               COALESCE(SUM(i.quantity) FILTER (
                   WHERE i.sale_date > (SELECT last_day FROM anchor) - (2 * %(days)s)::int
                     AND i.sale_date <= (SELECT last_day FROM anchor) - %(days)s::int
               ), 0) AS previous_units
        FROM products p
        LEFT JOIN sale_items i ON i.product_id = p.id
        WHERE p.store_id = %(store_id)s
        GROUP BY p.category
        ORDER BY current_units DESC
        """,
        {"store_id": store_id, "days": days},
    )


def daily_totals(store_id: int, days: int = 30) -> list[dict[str, Any]]:
    """Total units sold per day across the whole catalogue."""
    return query_all(
        """
        WITH anchor AS (
            SELECT COALESCE(MAX(sale_date), CURRENT_DATE) AS last_day
            FROM sale_items WHERE store_id = %(store_id)s
        )
        SELECT sale_date, SUM(quantity) AS quantity
        FROM sale_items
        WHERE store_id = %(store_id)s
          AND sale_date > (SELECT last_day FROM anchor) - %(days)s::int
        GROUP BY sale_date
        ORDER BY sale_date
        """,
        {"store_id": store_id, "days": days},
    )


# --------------------------------------------------------------------------
# Invoices
# --------------------------------------------------------------------------


def next_invoice_number(conn: Connection, store_id: int, prefix: str) -> str:
    """Sequential per-store invoice number.

    Derived from the row count inside the checkout transaction, so two
    concurrent checkouts cannot mint the same number — the second blocks on the
    unique index and retries.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS total FROM sales WHERE store_id = %s", (store_id,)
        )
        sequence = int(cur.fetchone()["total"]) + 1
    return f"{prefix}-{sequence:05d}"


def get_sale(sale_id: int, store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"SELECT {SALE_COLUMNS} FROM sales WHERE id = %s AND store_id = %s",
        (sale_id, store_id),
    )


def get_sale_items(sale_id: int, store_id: int) -> list[dict[str, Any]]:
    return query_all(
        f"SELECT {ITEM_COLUMNS} FROM sale_items WHERE sale_id = %s AND store_id = %s "
        f"ORDER BY id",
        (sale_id, store_id),
    )


def get_payments(sale_id: int, store_id: int) -> list[dict[str, Any]]:
    return query_all(
        "SELECT id, sale_id, store_id, method, amount, reference, created_at "
        "FROM payments WHERE sale_id = %s AND store_id = %s ORDER BY id",
        (sale_id, store_id),
    )


def _sale_filters(
    store_id: int,
    start_date: date | None,
    end_date: date | None,
    payment_method: str | None,
    status: str | None,
    customer_id: int | None,
    search: str | None,
) -> tuple[list[str], list[Any]]:
    clauses = ["s.store_id = %s"]
    params: list[Any] = [store_id]

    if start_date:
        clauses.append("s.sale_date >= %s")
        params.append(start_date)
    if end_date:
        clauses.append("s.sale_date <= %s")
        params.append(end_date)
    if payment_method:
        clauses.append("s.payment_method = %s")
        params.append(payment_method)
    if status:
        clauses.append("s.status = %s")
        params.append(status)
    if customer_id is not None:
        clauses.append("s.customer_id = %s")
        params.append(customer_id)
    if search:
        clauses.append("(s.invoice_number ILIKE %s OR s.customer_name ILIKE %s "
                       "OR s.customer_phone ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    return clauses, params


def list_sales(
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    payment_method: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses, params = _sale_filters(
        store_id, start_date, end_date, payment_method, status, customer_id, search
    )
    params.extend([limit, offset])
    return query_all(
        f"""
        SELECT s.id, s.store_id, s.invoice_number, s.customer_id, s.customer_name,
               s.customer_phone, s.subtotal, s.discount, s.tax, s.total, s.cost_total,
               s.payment_method, s.amount_received, s.change_due, s.status, s.notes,
               s.sale_date, s.created_by, s.created_at,
               COALESCE(counts.item_count, 0) AS item_count,
               COALESCE(counts.unit_count, 0) AS unit_count,
               u.full_name AS created_by_name
        FROM sales s
        LEFT JOIN (
            SELECT sale_id, COUNT(*) AS item_count, SUM(quantity) AS unit_count
            FROM sale_items GROUP BY sale_id
        ) counts ON counts.sale_id = s.id
        LEFT JOIN users u ON u.id = s.created_by
        WHERE {' AND '.join(clauses)}
        ORDER BY s.created_at DESC, s.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )


def count_sales(
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    payment_method: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    search: str | None = None,
) -> int:
    clauses, params = _sale_filters(
        store_id, start_date, end_date, payment_method, status, customer_id, search
    )
    row = query_one(
        f"SELECT COUNT(*) AS total FROM sales s WHERE {' AND '.join(clauses)}", tuple(params)
    )
    return int(row["total"]) if row else 0


def set_status(sale_id: int, store_id: int, status: str) -> dict[str, Any] | None:
    return query_one(
        f"UPDATE sales SET status = %s WHERE id = %s AND store_id = %s RETURNING {SALE_COLUMNS}",
        (status, sale_id, store_id),
    )


# --------------------------------------------------------------------------
# Business analytics
# --------------------------------------------------------------------------


def kpis(store_id: int, start_date: date, end_date: date) -> dict[str, Any]:
    """Revenue, orders, units and cost of goods sold for a period.

    Gross profit here is revenue net of tax minus COGS — tax collected is not
    the shop's money, so counting it as revenue would overstate the margin.
    """
    return query_one(
        """
        SELECT COUNT(*)                                   AS orders,
               COALESCE(SUM(total), 0)                    AS revenue,
               COALESCE(SUM(tax), 0)                      AS tax,
               COALESCE(SUM(discount), 0)                 AS discount,
               COALESCE(SUM(cost_total), 0)               AS cost_of_goods,
               COALESCE(AVG(total), 0)                    AS average_order_value,
               COALESCE((SELECT SUM(i.quantity) FROM sale_items i
                          JOIN sales s2 ON s2.id = i.sale_id
                         WHERE s2.store_id = %(store_id)s AND s2.status = 'COMPLETED'
                           AND s2.sale_date BETWEEN %(start)s AND %(end)s), 0) AS units
        FROM sales
        WHERE store_id = %(store_id)s AND status = 'COMPLETED'
          AND sale_date BETWEEN %(start)s AND %(end)s
        """,
        {"store_id": store_id, "start": start_date, "end": end_date},
    )


def revenue_series(store_id: int, start_date: date, end_date: date) -> list[dict[str, Any]]:
    """Revenue, orders and profit per day.

    generate_series fills days with no sales as zeros, so the chart shows a
    closed shop as a flat line rather than skipping the day entirely.
    """
    return query_all(
        """
        SELECT day::date                            AS date,
               COALESCE(SUM(s.total), 0)            AS revenue,
               COALESCE(SUM(s.cost_total), 0)       AS cost,
               COALESCE(SUM(s.tax), 0)              AS tax,
               COUNT(s.id)                          AS orders
        FROM generate_series(%(start)s::date, %(end)s::date, '1 day') AS day
        LEFT JOIN sales s
               ON s.sale_date = day::date
              AND s.store_id = %(store_id)s
              AND s.status = 'COMPLETED'
        GROUP BY day
        ORDER BY day
        """,
        {"store_id": store_id, "start": start_date, "end": end_date},
    )


def payment_split(store_id: int, start_date: date, end_date: date) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT payment_method, COUNT(*) AS orders, COALESCE(SUM(total), 0) AS revenue
        FROM sales
        WHERE store_id = %s AND status = 'COMPLETED' AND sale_date BETWEEN %s AND %s
        GROUP BY payment_method
        ORDER BY revenue DESC
        """,
        (store_id, start_date, end_date),
    )


def recent_sales(store_id: int, limit: int = 8) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT s.id, s.invoice_number, s.total, s.payment_method, s.customer_name,
               s.status, s.created_at,
               COALESCE(SUM(i.quantity), 0) AS unit_count
        FROM sales s
        LEFT JOIN sale_items i ON i.sale_id = s.id
        WHERE s.store_id = %s
        GROUP BY s.id
        ORDER BY s.created_at DESC
        LIMIT %s
        """,
        (store_id, limit),
    )


def product_performance(
    store_id: int, start_date: date, end_date: date, limit: int = 500
) -> list[dict[str, Any]]:
    """Units, revenue, cost and profit per product for a period."""
    return query_all(
        """
        SELECT p.id AS product_id, p.sku, p.name, p.category, p.current_stock,
               p.cost_price, p.selling_price,
               COALESCE(SUM(i.quantity), 0)                   AS total_units,
               COALESCE(SUM(i.line_total), 0)                 AS total_revenue,
               COALESCE(SUM(i.quantity * i.cost_price), 0)    AS total_cost,
               COALESCE(SUM(i.line_total - i.tax_amount
                            - i.quantity * i.cost_price), 0)  AS gross_profit
        FROM products p
        LEFT JOIN sale_items i
               ON i.product_id = p.id AND i.sale_date BETWEEN %(start)s AND %(end)s
        LEFT JOIN sales s ON s.id = i.sale_id AND s.status = 'COMPLETED'
        WHERE p.store_id = %(store_id)s AND p.is_active = TRUE
        GROUP BY p.id
        ORDER BY total_revenue DESC
        LIMIT %(limit)s
        """,
        {"store_id": store_id, "start": start_date, "end": end_date, "limit": limit},
    )


def tax_summary(store_id: int, start_date: date, end_date: date) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT i.tax_rate,
               COALESCE(SUM(i.line_total - i.tax_amount), 0) AS taxable_value,
               COALESCE(SUM(i.tax_amount), 0)                AS tax_collected,
               COUNT(DISTINCT i.sale_id)                     AS invoices
        FROM sale_items i
        JOIN sales s ON s.id = i.sale_id
        WHERE i.store_id = %s AND s.status = 'COMPLETED' AND i.sale_date BETWEEN %s AND %s
        GROUP BY i.tax_rate
        ORDER BY i.tax_rate
        """,
        (store_id, start_date, end_date),
    )
