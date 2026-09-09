"""Demand analytics: anomalies, movers and category trends.

Anomaly detection here is deliberately statistical rather than a second model.
The question "is this week unusual for this product?" is answered by comparing
recent demand against that product's own recent history — Pandas and NumPy are
the right tools, and a trained model would add opacity without adding accuracy.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from app.config import get_settings
from app.ml.feature_engineering import build_daily_frame
from app.models import product as product_model
from app.models import sale as sale_model
from app.services import inventory_service

logger = logging.getLogger(__name__)


def _daily_series(history: list[dict[str, Any]]) -> pd.Series:
    """Gap-free daily demand indexed by date."""
    frame = build_daily_frame(history)
    if frame.empty:
        return pd.Series(dtype=float)
    return frame.set_index("sale_date")["quantity"].astype(float)


def detect_anomaly(
    history: list[dict[str, Any]],
    product: dict[str, Any],
    settings=None,
) -> dict[str, Any] | None:
    """Compare recent demand against the baseline window before it.

    Two gates must both be cleared. The percentage change filters out
    statistically significant but commercially irrelevant moves; the z-score
    filters out large-looking swings on products that always swing that much.
    Returns None when the product looks normal.
    """
    settings = settings or get_settings()
    series = _daily_series(history)

    recent_days = settings.anomaly_recent_days
    baseline_days = settings.anomaly_baseline_days
    if len(series) < recent_days + baseline_days:
        return None

    recent = series.iloc[-recent_days:]
    baseline = series.iloc[-(recent_days + baseline_days) : -recent_days]

    recent_mean = float(recent.mean())
    baseline_mean = float(baseline.mean())
    baseline_std = float(baseline.std(ddof=1))

    if baseline_mean <= 0:
        # Nothing sold in the baseline window: a jump from zero is real news,
        # but a percentage change against zero is undefined.
        if recent_mean <= 0:
            return None
        change = None
    else:
        change = (recent_mean - baseline_mean) / baseline_mean

    # Standard error of a mean over `recent_days` observations.
    if baseline_std > 0:
        z_score = (recent_mean - baseline_mean) / (baseline_std / math.sqrt(recent_days))
    else:
        z_score = 0.0 if recent_mean == baseline_mean else math.inf

    if change is not None and abs(change) < settings.anomaly_min_change:
        return None
    if abs(z_score) < settings.anomaly_min_zscore:
        return None

    direction = "SPIKE" if recent_mean > baseline_mean else "DROP"
    severity = "HIGH" if abs(z_score) >= 4.0 else "MEDIUM"

    if change is None:
        message = (
            f"{product['name']} sold {recent_mean:.1f} units/day over the last "
            f"{recent_days} days after selling nothing in the previous "
            f"{baseline_days}."
        )
    else:
        verb = "increased" if direction == "SPIKE" else "decreased"
        message = (
            f"{product['name']} demand {verb} {abs(change) * 100:.0f}% compared "
            f"with its recent average."
        )

    return {
        "product_id": product["id"],
        "sku": product["sku"],
        "name": product["name"],
        "category": product["category"],
        "direction": direction,
        "severity": severity,
        "recent_daily_average": round(recent_mean, 2),
        "baseline_daily_average": round(baseline_mean, 2),
        "change_pct": round(change * 100, 1) if change is not None else None,
        "z_score": round(z_score, 2) if math.isfinite(z_score) else None,
        "recent_days": recent_days,
        "baseline_days": baseline_days,
        "message": message,
    }


def detect_anomalies(limit: int | None = None) -> list[dict[str, Any]]:
    """Scan the catalogue, strongest deviation first."""
    settings = get_settings()
    found: list[dict[str, Any]] = []

    for product in product_model.list_products(limit=1000):
        history = sale_model.daily_history(product["id"])
        if not history:
            continue
        anomaly = detect_anomaly(history, product, settings)
        if anomaly:
            found.append(anomaly)

    found.sort(key=lambda row: abs(row["z_score"] or 0), reverse=True)
    return found[:limit] if limit else found


# --------------------------------------------------------------------------
# Movers
# --------------------------------------------------------------------------


def product_demand_table(days: int = 30) -> pd.DataFrame:
    """Units and revenue per product over the trailing window."""
    rows = sale_model.recent_totals(days)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def top_products(days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
    """Best sellers by units over the trailing window."""
    frame = product_demand_table(days)
    if frame.empty:
        return []
    frame = frame.sort_values("total_units", ascending=False).head(limit)
    return _movers_payload(frame, days)


def slow_moving(days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
    """Products selling well below the catalogue average.

    Products with no sales at all in the window are included first — they are
    the clearest case of dead stock.
    """
    settings = get_settings()
    frame = product_demand_table(days)
    if frame.empty:
        return []

    average = frame["total_units"].mean()
    cutoff = average * settings.slow_moving_threshold
    frame = frame[frame["total_units"] <= cutoff].sort_values("total_units")
    return _movers_payload(frame.head(limit), days)


def _movers_payload(frame: pd.DataFrame, days: int) -> list[dict[str, Any]]:
    return [
        {
            "product_id": int(row["product_id"]),
            "sku": row["sku"],
            "name": row["name"],
            "category": row["category"],
            "total_units": int(row["total_units"]),
            "total_revenue": round(float(row["total_revenue"]), 2),
            "daily_average": round(float(row["total_units"]) / days, 2),
            "current_stock": int(row["current_stock"]),
        }
        for _, row in frame.iterrows()
    ]


# --------------------------------------------------------------------------
# Category trends
# --------------------------------------------------------------------------


def category_trends(days: int = 30) -> list[dict[str, Any]]:
    """Per-category demand now versus the equivalent window before it."""
    rows = sale_model.category_totals(days)
    if not rows:
        return []

    frame = pd.DataFrame(rows)
    trends = []
    for _, row in frame.iterrows():
        current = float(row["current_units"])
        previous = float(row["previous_units"])
        change = ((current - previous) / previous * 100) if previous > 0 else None
        trends.append(
            {
                "category": row["category"],
                "current_units": int(current),
                "previous_units": int(previous),
                "change_pct": round(change, 1) if change is not None else None,
                "direction": "UP" if current > previous else "DOWN" if current < previous else "FLAT",
                "daily_average": round(current / days, 2),
            }
        )

    trends.sort(key=lambda row: row["current_units"], reverse=True)
    return trends


# --------------------------------------------------------------------------
# Catalogue demand trend
# --------------------------------------------------------------------------


def demand_trend(history_days: int = 30, forecast_days: int = 7) -> dict[str, Any]:
    """Total daily demand across the catalogue: observed, then predicted.

    Aggregating the per-SKU forecasts is what makes the dashboard chart cheap —
    the forecasts are already cached from the recommendations request.
    """
    from app.services import forecast_service

    observed = sale_model.daily_totals(history_days)
    history = [
        {"date": row["sale_date"].isoformat(), "quantity": int(row["quantity"])}
        for row in observed
    ]

    per_product = forecast_service.forecast_catalogue(days=forecast_days)
    totals: dict[str, int] = {}
    for rows in per_product.values():
        for row in rows:
            totals[row["date"]] = totals.get(row["date"], 0) + row["predicted_demand"]

    forecast = [
        {"date": day, "predicted_demand": totals[day]} for day in sorted(totals)
    ]
    return {"history": history, "forecast": forecast}


# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------


def overview(anomaly_limit: int = 5) -> dict[str, Any]:
    """Everything the dashboard landing page needs, in one request."""
    recommendations = inventory_service.recommendations()
    summary = inventory_service.summarise(recommendations)
    anomalies = detect_anomalies()

    return {
        **summary,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies[:anomaly_limit],
        "top_reorders": recommendations[:5],
    }
