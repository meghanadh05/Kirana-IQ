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
    MODEL_PATH,
    InsufficientHistoryError,
    ModelNotTrainedError,
    forecast as run_forecast,
    model_info,
)
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


def _cache_key(product_id: int, history: list[dict[str, Any]]) -> tuple:
    """Cache identity: the product, its latest data, and the model file.

    Including the last sale date and the row count means a new sale invalidates
    the entry; including the model's mtime means retraining does too.
    """
    last_date = max(row["sale_date"] for row in history)
    model_mtime = MODEL_PATH.stat().st_mtime if MODEL_PATH.exists() else 0.0
    return (product_id, str(last_date), len(history), model_mtime)


def forecast_product(
    product: dict[str, Any],
    days: int = 7,
    history: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Forecast one product, using the cache when possible."""
    if days < 1 or days > MAX_FORECAST_DAYS:
        raise ValueError(f"days must be between 1 and {MAX_FORECAST_DAYS}")

    history = sale_model.daily_history(product["id"]) if history is None else history
    if not history:
        raise InsufficientHistoryError(f"Product {product['id']} has no sales history")

    key = _cache_key(product["id"], history)
    cached = _cache.get(key)
    if cached and cached[0] >= days:
        return cached[1][:days]

    rows = run_forecast(history, product, days=days, events=_events())
    _cache[key] = (days, rows)
    return rows


def forecast_by_id(product_id: int, days: int = 7) -> dict[str, Any]:
    """Full forecast response for one product id."""
    product = product_model.get_product(product_id)
    if product is None:
        return {}

    rows = forecast_product(product, days=days)
    return {
        "product_id": product["id"],
        "sku": product["sku"],
        "name": product["name"],
        "forecast_days": days,
        "total_predicted_demand": sum(r["predicted_demand"] for r in rows),
        "forecast": rows,
    }


def forecast_catalogue(days: int = 7) -> dict[int, list[dict[str, Any]]]:
    """Forecast every product that has enough history.

    Products with too little history are skipped rather than failing the whole
    request — a newly added SKU should not break the dashboard.
    """
    results: dict[int, list[dict[str, Any]]] = {}
    for product in product_model.list_products(limit=1000):
        try:
            results[product["id"]] = forecast_product(product, days=days)
        except (InsufficientHistoryError, ModelNotTrainedError) as exc:
            logger.info("Skipping product %s: %s", product["id"], exc)
    return results


def history_series(product_id: int, days: int = 60) -> list[dict[str, Any]]:
    """Recent observed demand, for plotting alongside the forecast."""
    rows = sale_model.daily_history(product_id)
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


def training_status() -> dict[str, Any]:
    """What the API knows about the current model."""
    info = model_info()
    return {"trained": info is not None, **(info or {})}


def retrain() -> dict[str, Any]:
    """Retrain from current database contents and invalidate cached forecasts."""
    from app.ml.train_model import train

    report = train(save=True)
    # The model loader is cached on (path, mtime), so a freshly written file is
    # picked up automatically; only the forecast cache needs clearing.
    clear_cache()
    return report
