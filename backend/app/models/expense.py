"""SQL access for expenses."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.database import execute, query_all, query_one

CATEGORIES = ("Rent", "Electricity", "Salaries", "Transport", "Maintenance", "Other")

COLUMNS = """
    id, store_id, category, description, amount, expense_date, payment_method,
    notes, created_by, created_at
"""


def list_expenses(
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses, params = _filters(store_id, start_date, end_date, category)
    params.extend([limit, offset])
    return query_all(
        f"SELECT {COLUMNS} FROM expenses WHERE {' AND '.join(clauses)} "
        f"ORDER BY expense_date DESC, id DESC LIMIT %s OFFSET %s",
        tuple(params),
    )


def count_expenses(
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
) -> int:
    clauses, params = _filters(store_id, start_date, end_date, category)
    row = query_one(
        f"SELECT COUNT(*) AS total FROM expenses WHERE {' AND '.join(clauses)}", tuple(params)
    )
    return int(row["total"]) if row else 0


def _filters(
    store_id: int, start_date: date | None, end_date: date | None, category: str | None
) -> tuple[list[str], list[Any]]:
    clauses = ["store_id = %s"]
    params: list[Any] = [store_id]
    if start_date:
        clauses.append("expense_date >= %s")
        params.append(start_date)
    if end_date:
        clauses.append("expense_date <= %s")
        params.append(end_date)
    if category:
        clauses.append("category = %s")
        params.append(category)
    return clauses, params


def get(expense_id: int, store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"SELECT {COLUMNS} FROM expenses WHERE id = %s AND store_id = %s",
        (expense_id, store_id),
    )


def create(store_id: int, data: dict[str, Any], user_id: int) -> dict[str, Any]:
    return query_one(
        f"""
        INSERT INTO expenses (store_id, category, description, amount, expense_date,
                              payment_method, notes, created_by)
        VALUES (%(store_id)s, %(category)s, %(description)s, %(amount)s, %(expense_date)s,
                %(payment_method)s, %(notes)s, %(created_by)s)
        RETURNING {COLUMNS}
        """,
        {**data, "store_id": store_id, "created_by": user_id},
    )


def update(expense_id: int, store_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    allowed = ("category", "description", "amount", "expense_date", "payment_method", "notes")
    fields = {key: value for key, value in data.items() if key in allowed}
    if not fields:
        return get(expense_id, store_id)

    assignments = ", ".join(f"{key} = %({key})s" for key in fields)
    return query_one(
        f"UPDATE expenses SET {assignments} WHERE id = %(expense_id)s "
        f"AND store_id = %(store_id)s RETURNING {COLUMNS}",
        {**fields, "expense_id": expense_id, "store_id": store_id},
    )


def delete(expense_id: int, store_id: int) -> int:
    return execute("DELETE FROM expenses WHERE id = %s AND store_id = %s", (expense_id, store_id))


def totals_by_category(
    store_id: int, start_date: date | None = None, end_date: date | None = None
) -> list[dict[str, Any]]:
    clauses, params = _filters(store_id, start_date, end_date, None)
    return query_all(
        f"""
        SELECT category, SUM(amount) AS total, COUNT(*) AS entries
        FROM expenses WHERE {' AND '.join(clauses)}
        GROUP BY category ORDER BY total DESC
        """,
        tuple(params),
    )


def total_amount(
    store_id: int, start_date: date | None = None, end_date: date | None = None
) -> float:
    clauses, params = _filters(store_id, start_date, end_date, None)
    row = query_one(
        f"SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        f"WHERE {' AND '.join(clauses)}",
        tuple(params),
    )
    return float(row["total"]) if row else 0.0
