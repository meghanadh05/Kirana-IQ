"""Forecasting orchestration: database in, forecast out.

Recursive forecasting is not cheap — every step rebuilds the lag features and
calls the model. A whole-catalogue forecast costs seconds, so results are cached
in process and invalidated by the things that can actually change them: new
sales for the product, or a retrained model.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from app.ml.feature_engineering import load_events
from app.ml.predict import (
    InsufficientHistoryError,
    ModelNotTrainedError,
    forecast as run_forecast,
    load_model,
    model_info,
    resolve_model_path,
)
from app.database import query_one
from app.models import forecast_run as forecast_run_model
from app.models import product as product_model
from app.models import sale as sale_model

logger = logging.getLogger(__name__)

MAX_FORECAST_DAYS = 30

# key -> (horizon, rows). A cached longer horizon serves any shorter request.
_cache: dict[tuple, tuple[int, list[dict[str, Any]]]] = {}
_events_cache: pd.DataFrame | None = None


def _events() -> pd.DataFrame:
    global _events_cache
    if _events_cache is None:
        _events_cache = load_events()
    return _events_cache


def clear_cache() -> None:
    """Drop cached forecasts. Called after training."""
    global _events_cache
    _cache.clear()
    _events_cache = None


def _cache_key(store_id: int, product_id: int, history: list[dict[str, Any]]) -> tuple:
    """Cache identity: the store, the product, its latest data, and the model file.

    Including the last sale date and the row count means a new sale invalidates
    the entry; including the model's mtime means retraining does too. The store
    id is part of the key so two tenants can never read each other's forecasts.
    """
    last_date = max(row["sale_date"] for row in history)
    path = resolve_model_path(store_id)
    model_mtime = path.stat().st_mtime if path.exists() else 0.0
    return (store_id, product_id, str(last_date), len(history), model_mtime)


def forecast_product(
    product: dict[str, Any],
    store_id: int,
    days: int = 7,
    history: list[dict[str, Any]] | None = None,
    model_bundle: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Forecast one product, using the cache when possible."""
    if days < 1 or days > MAX_FORECAST_DAYS:
        raise ValueError(f"days must be between 1 and {MAX_FORECAST_DAYS}")

    history = sale_model.daily_history(product["id"], store_id) if history is None else history
    if not history:
        raise InsufficientHistoryError(f"{product['name']} has no sales history yet")

    key = _cache_key(store_id, product["id"], history)
    cached = _cache.get(key)
    if cached and cached[0] >= days:
        return cached[1][:days]

    bundle = model_bundle or load_model(store_id)
    rows = run_forecast(history, product, days=days, events=_events(), model_bundle=bundle)
    _cache[key] = (days, rows)
    return rows


def forecast_by_id(product_id: int, store_id: int, days: int = 7) -> dict[str, Any]:
    """Full forecast response for one product id."""
    product = product_model.get_product(product_id, store_id)
    if product is None:
        return {}

    rows = forecast_product(product, store_id, days=days)
    return {
        "product_id": product["id"],
        "sku": product["sku"],
        "name": product["name"],
        "forecast_days": days,
        "total_predicted_demand": sum(r["predicted_demand"] for r in rows),
        "forecast": rows,
    }


def forecast_catalogue(store_id: int, days: int = 7) -> dict[int, list[dict[str, Any]]]:
    """Forecast every product in a store that has enough history.

    Products with too little history are skipped rather than failing the whole
    request — a newly added SKU should not break the dashboard.
    """
    results: dict[int, list[dict[str, Any]]] = {}
    try:
        bundle = load_model(store_id)
    except ModelNotTrainedError as exc:
        logger.info("No model for store %s: %s", store_id, exc)
        return results

    for product in product_model.list_products(store_id, limit=1000):
        try:
            results[product["id"]] = forecast_product(
                product, store_id, days=days, model_bundle=bundle
            )
        except (InsufficientHistoryError, ModelNotTrainedError) as exc:
            logger.info("Skipping product %s: %s", product["id"], exc)
    return results


def history_series(product_id: int, store_id: int, days: int = 60) -> list[dict[str, Any]]:
    """Recent observed demand, for plotting alongside the forecast."""
    rows = sale_model.daily_history(product_id, store_id)
    if not rows:
        return []

    frame = pd.DataFrame(rows)
    frame["sale_date"] = pd.to_datetime(frame["sale_date"])

    # Reindex so zero-sale days appear in the chart as zeros, not as gaps.
    calendar = pd.date_range(frame["sale_date"].max() - pd.Timedelta(days=days - 1),
                             frame["sale_date"].max(), freq="D")
    series = (
        frame.set_index("sale_date")["quantity"]
        .reindex(calendar, fill_value=0)
        .astype(float)
    )
    return [
        {"date": index.date().isoformat(), "quantity": int(value)}
        for index, value in series.items()
    ]


def training_status(store_id: int) -> dict[str, Any]:
    """What the API knows about this store's model, plus its last training run."""
    info = model_info(store_id)
    last_run = forecast_run_model.latest(store_id)
    return {
        "trained": info is not None,
        **(info or {}),
        "last_run": last_run,
        "history_days": _history_span_days(store_id),
    }


def _history_span_days(store_id: int) -> int:
    """Calendar days of sales history available to train on."""
    row = query_one(
        "SELECT MIN(sale_date) AS first, MAX(sale_date) AS last "
        "FROM sale_items WHERE store_id = %s",
        (store_id,),
    )
    if not row or row["first"] is None:
        return 0
    return (row["last"] - row["first"]).days + 1


def retrain(store_id: int, user_id: int | None = None) -> dict[str, Any]:
    """Retrain this store's model and invalidate its cached forecasts.

    Synchronous today. The run is recorded in `forecast_runs` first and closed
    out afterwards, which is the shape a background worker would need — moving
    it off the request thread later means changing who calls this, not how it
    reports.
    """
    from app.ml.train_model import train

    run_id = forecast_run_model.start(store_id, user_id)
    try:
        report = train(store_id, save=True)
    except Exception as exc:
        forecast_run_model.fail(run_id, str(exc))
        raise

    forecast_run_model.finish(
        run_id,
        model_name=report["selected_model"],
        rows_used=report["rows"]["total"],
        products=report["products"],
        metrics=report["test_scores"],
    )
    # The model loader is cached on (path, mtime), so a freshly written file is
    # picked up automatically; only the forecast cache needs clearing.
    clear_cache()
    return report
