"""SQL access for forecast training runs.

Recording runs gives the Forecasting screen something honest to show — when the
model was last trained, on how much data, and what it scored — instead of a bare
"retrain" button with no feedback.
"""

from __future__ import annotations

import json
from typing import Any

from app.database import execute, query_one

COLUMNS = """
    id, store_id, status, model_name, rows_used, products, metrics, error,
    started_at, finished_at, created_by
"""


def start(store_id: int, created_by: int | None = None) -> int:
    row = query_one(
        "INSERT INTO forecast_runs (store_id, status, created_by) "
        "VALUES (%s, 'RUNNING', %s) RETURNING id",
        (store_id, created_by),
    )
    return int(row["id"])


def finish(
    run_id: int,
    model_name: str,
    rows_used: int,
    products: int,
    metrics: dict[str, Any],
) -> int:
    return execute(
        """
        UPDATE forecast_runs
           SET status = 'COMPLETED', model_name = %s, rows_used = %s, products = %s,
               metrics = %s, finished_at = NOW()
         WHERE id = %s
        """,
        (model_name, rows_used, products, json.dumps(metrics, default=float), run_id),
    )


def fail(run_id: int, error: str) -> int:
    return execute(
        "UPDATE forecast_runs SET status = 'FAILED', error = %s, finished_at = NOW() "
        "WHERE id = %s",
        (error[:500], run_id),
    )


def latest(store_id: int) -> dict[str, Any] | None:
    return query_one(
        f"SELECT {COLUMNS} FROM forecast_runs WHERE store_id = %s "
        f"ORDER BY started_at DESC LIMIT 1",
        (store_id,),
    )
