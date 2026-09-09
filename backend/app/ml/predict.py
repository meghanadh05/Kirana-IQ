"""Multi-day demand forecasting with the trained model.

The model predicts one day ahead. Longer horizons are produced recursively:
predict tomorrow, append that prediction to the history as if it were observed,
rebuild the lag features, predict the day after, and so on.

That is the standard approach for a single-step model, and it has a real cost —
each step builds on the previous step's estimate, so error compounds with the
horizon. `evaluate_horizon` in this module measures exactly how much.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.config import MODEL_DIR

from app.ml.feature_engineering import (
    FEATURE_COLUMNS,
    FEATURE_LOOKBACK_DAYS,
    MIN_HISTORY_DAYS,
    build_features,
    load_events,
)

logger = logging.getLogger(__name__)

MODEL_PATH = MODEL_DIR / "demand_model.joblib"


def model_path(store_id: int | None = None) -> Path:
    """Where a store's model lives.

    Each store trains on its own sales, so each gets its own artefact. Passing
    None addresses the shared model, which is what a freshly created store uses
    until it has trained one of its own.
    """
    if store_id is None:
        return MODEL_PATH
    return MODEL_DIR / f"store_{store_id}" / "demand_model.joblib"


def resolve_model_path(store_id: int | None = None) -> Path:
    """The store's own model when it has one, otherwise the shared model."""
    candidate = model_path(store_id)
    return candidate if candidate.exists() else MODEL_PATH

SUPPORTED_HORIZONS = (7, 14, 30)


class ModelNotTrainedError(RuntimeError):
    """Raised when a forecast is requested before any model has been trained."""


class InsufficientHistoryError(ValueError):
    """Raised when a product has too little history to build features."""


@lru_cache(maxsize=1)
def _load_bundle(path_str: str, mtime: float) -> dict[str, Any]:
    """Load and cache the model. `mtime` busts the cache after retraining."""
    return joblib.load(path_str)


def load_model(store_id: int | None = None) -> dict[str, Any]:
    """Return the saved model bundle, reloading it if the file changed."""
    path = resolve_model_path(store_id)
    if not path.exists():
        raise ModelNotTrainedError(
            "No trained model yet. Train one from Forecasting → Retrain Model."
        )
    return _load_bundle(str(path), path.stat().st_mtime)


def model_info(store_id: int | None = None) -> dict[str, Any] | None:
    """Metadata about the current model, or None when untrained."""
    try:
        bundle = load_model(store_id)
    except ModelNotTrainedError:
        return None
    return {
        "model_name": bundle["model_name"],
        "trained_at": bundle["trained_at"],
        "metrics": bundle["metrics"],
        "features": len(bundle["feature_columns"]),
        "store_specific": model_path(store_id).exists() if store_id else False,
        "training_rows": bundle.get("training_rows"),
        "training_days": bundle.get("training_days"),
        "products": bundle.get("products"),
    }


def _history_span_days(history: list[dict[str, Any]]) -> int:
    """Calendar days covered by a sparse history, inclusive of both ends."""
    dates = [pd.Timestamp(row["sale_date"]) for row in history]
    return (max(dates) - min(dates)).days + 1


def forecast(
    history: list[dict[str, Any]],
    product: dict[str, Any],
    days: int = 7,
    events: pd.DataFrame | None = None,
    model_bundle: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Forecast daily demand for the next `days` days.

    Returns one entry per day: the date and the predicted units, clipped at zero
    and rounded to whole units — a shop orders packets, not fractions.
    """
    if days < 1:
        raise ValueError("days must be at least 1")
    if not history:
        raise InsufficientHistoryError("Product has no sales history")

    # Measured as a calendar span, not a row count: a product with zero-sale
    # days has fewer rows than days, and the lag windows care about days.
    span = _history_span_days(history)
    if span < MIN_HISTORY_DAYS:
        raise InsufficientHistoryError(
            f"Product needs at least {MIN_HISTORY_DAYS} days of history, spans {span}"
        )

    bundle = model_bundle or load_model()
    model = bundle["model"]
    columns = bundle.get("feature_columns", FEATURE_COLUMNS)
    events = load_events() if events is None else events

    # Working copy of the observed series; predictions are appended to it.
    records = [
        {
            "sale_date": pd.Timestamp(row["sale_date"]),
            "quantity": float(row["quantity"]),
            "avg_price": row.get("avg_price"),
        }
        for row in history
    ]
    last_observed = max(r["sale_date"] for r in records)

    # Trim to the deepest window any feature reads. Older rows provably cannot
    # affect the result, and rebuilding a 70-row frame per step instead of a
    # 365-row one is what makes a whole-catalogue forecast fast enough to serve.
    horizon_start = last_observed - timedelta(days=FEATURE_LOOKBACK_DAYS + 9)
    records = [r for r in records if r["sale_date"] >= horizon_start]

    predictions: list[dict[str, Any]] = []

    for step in range(1, days + 1):
        target_date = last_observed + timedelta(days=step)

        # Append the target day with a placeholder. No feature for a given row
        # reads that row's own quantity, so the placeholder cannot leak.
        working = records + [
            {"sale_date": target_date, "quantity": 0.0, "avg_price": None}
        ]
        frame = build_features(working, product, events=events, dropna=False)

        row = frame[frame["sale_date"] == target_date]
        if row.empty:
            raise InsufficientHistoryError(f"Could not build features for {target_date.date()}")

        features = row[columns].astype(float)
        if features.isna().any().any():
            raise InsufficientHistoryError(
                "Feature window incomplete; the product needs a longer unbroken history"
            )

        predicted = float(np.clip(model.predict(features)[0], 0, None))

        # Feed the prediction back in so the next step's lags are populated.
        records.append(
            {"sale_date": target_date, "quantity": predicted, "avg_price": None}
        )
        predictions.append(
            {"date": target_date.date().isoformat(), "predicted_demand": int(round(predicted))}
        )

    return predictions


def forecast_units(
    history: list[dict[str, Any]],
    product: dict[str, Any],
    days: int = 7,
    events: pd.DataFrame | None = None,
    model_bundle: dict[str, Any] | None = None,
) -> float:
    """Total predicted units over the horizon — the input to inventory maths."""
    rows = forecast(history, product, days=days, events=events, model_bundle=model_bundle)
    return float(sum(row["predicted_demand"] for row in rows))


def evaluate_horizon(
    history: list[dict[str, Any]],
    product: dict[str, Any],
    horizon: int = 7,
    origins: int = 8,
    events: pd.DataFrame | None = None,
    model_bundle: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Backtest recursive forecasting at a real horizon.

    Walks backwards through the tail of the history, truncating at several
    origin dates, forecasting `horizon` days from each, and pairing every
    prediction with the actual value that followed. Returns one row per
    (origin, step) so error growth across the horizon can be measured.
    """
    bundle = model_bundle or load_model()
    events = load_events() if events is None else events

    ordered = sorted(history, key=lambda r: pd.Timestamp(r["sale_date"]))
    actual_by_date = {
        pd.Timestamp(row["sale_date"]).date(): float(row["quantity"]) for row in ordered
    }

    first_date = pd.Timestamp(ordered[0]["sale_date"])
    last_date = pd.Timestamp(ordered[-1]["sale_date"])
    results: list[dict[str, Any]] = []

    for index in range(origins):
        # Truncate by calendar date so gaps in the sales table cannot shift the
        # origin, and stop once the remaining window is too short for features.
        cutoff_date = last_date - timedelta(days=horizon * (index + 1))
        if (cutoff_date - first_date).days + 1 < MIN_HISTORY_DAYS:
            break

        truncated = [r for r in ordered if pd.Timestamp(r["sale_date"]) <= cutoff_date]
        if not truncated:
            break

        predictions = forecast(
            truncated, product, days=horizon, events=events, model_bundle=bundle
        )

        for step, prediction in enumerate(predictions, start=1):
            target = date.fromisoformat(prediction["date"])
            # Days absent from the sales table are genuine zero-sale days.
            results.append(
                {
                    "product_id": product.get("id"),
                    "origin": cutoff_date.date(),
                    "step": step,
                    "date": target,
                    "actual": actual_by_date.get(target, 0.0),
                    "predicted": float(prediction["predicted_demand"]),
                }
            )

    return results
