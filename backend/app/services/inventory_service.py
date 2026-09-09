"""Turn demand forecasts into inventory decisions.

This is where the project earns its name. A forecast on its own tells a shop
owner nothing actionable; what they need is "order 35 more units of milk today,
because you will run out before Thursday's delivery".

Every threshold comes from settings so the policy can be tuned without touching
this logic.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from app.config import get_settings
from app.ml.feature_engineering import build_daily_frame
from app.ml.predict import InsufficientHistoryError, ModelNotTrainedError
from app.models import product as product_model
from app.models import sale as sale_model
from app.services import forecast_service

logger = logging.getLogger(__name__)

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
RISK_ORDER = {level: index for index, level in enumerate(RISK_LEVELS)}


def demand_variability(history: list[dict[str, Any]], window: int = 30) -> float:
    """Standard deviation of recent daily demand, used to size safety stock.

    Computed on a zero-filled calendar: a day with no sales is a real zero and
    ignoring it would understate how erratic a product is.
    """
    frame = build_daily_frame(history)
    if frame.empty:
        return 0.0
    recent = frame.tail(window)["quantity"].to_numpy(dtype=float)
    if len(recent) < 2:
        return 0.0
    return float(np.std(recent, ddof=1))


def classify_risk(
    stock_cover_days: float | None,
    lead_time_days: int,
    settings=None,
) -> str:
    """Map stock cover onto a risk level.

    The ladder is deliberately lead-time relative: two days of cover is fine if
    the supplier delivers daily, and dangerous if they deliver weekly.
    """
    settings = settings or get_settings()

    if stock_cover_days is None:
        # No predicted demand: stock is not at risk of running out.
        return "LOW"
    if stock_cover_days <= settings.critical_cover_days:
        return "CRITICAL"
    if stock_cover_days <= lead_time_days:
        return "HIGH"
    if stock_cover_days <= lead_time_days + settings.medium_cover_buffer_days:
        return "MEDIUM"
    return "LOW"


def safety_stock(daily_std: float, cover_days: float, settings=None) -> float:
    """Buffer against demand variability over the replenishment window.

    Standard formula: z x sigma x sqrt(days). Errors accumulate with the square
    root of time, not linearly, so a 9-day window needs 3x the buffer of a
    1-day window, not 9x.
    """
    settings = settings or get_settings()
    return settings.service_level_z * daily_std * math.sqrt(max(cover_days, 0))


def build_reason(
    risk: str,
    overstock: bool,
    stock_cover_days: float | None,
    lead_time_days: int,
    reorder_quantity: int,
) -> str:
    """A plain-language explanation. The number alone is not a recommendation."""
    if stock_cover_days is None:
        return (
            "No demand predicted for this product, so current stock is not "
            "expected to run out."
        )

    cover = f"{stock_cover_days:.1f} day{'s' if stock_cover_days != 1 else ''}"

    if risk == "CRITICAL":
        return (
            f"Only {cover} of stock left and the supplier takes {lead_time_days} "
            f"days. This product will very likely run out before replenishment "
            f"arrives — reorder {reorder_quantity} units now."
        )
    if risk == "HIGH":
        return (
            f"Stock covers {cover} but the supplier lead time is "
            f"{lead_time_days} days, so current inventory may run out before "
            f"the next delivery. Reorder {reorder_quantity} units."
        )
    if risk == "MEDIUM":
        return (
            f"Stock covers {cover}, only just beyond the {lead_time_days}-day "
            f"lead time. Worth reordering {reorder_quantity} units soon."
        )
    if overstock:
        return (
            f"Stock covers {cover} of predicted demand, well beyond normal "
            f"requirements. Capital is tied up here — hold off on reordering."
        )
    return f"Stock covers {cover}, comfortably beyond the {lead_time_days}-day lead time."


def analyse(
    product: dict[str, Any],
    history: list[dict[str, Any]],
    forecast_rows: list[dict[str, Any]],
    settings=None,
) -> dict[str, Any]:
    """Full inventory assessment for one product.

    `forecast_rows` must cover at least lead_time + safety_days so the reorder
    quantity is based on predicted demand rather than an extrapolated average.
    """
    settings = settings or get_settings()

    current_stock = int(product["current_stock"])
    lead_time_days = int(product["lead_time_days"])
    replenishment_days = lead_time_days + settings.safety_days

    daily = [row["predicted_demand"] for row in forecast_rows]
    expected_7_day_demand = float(sum(daily[:7]))
    average_daily_demand = float(np.mean(daily)) if daily else 0.0

    # Demand across the window that matters for reordering: how much sells
    # between placing the order and the delivery landing, plus a safety margin.
    if len(daily) >= replenishment_days:
        lead_time_demand = float(sum(daily[:replenishment_days]))
    else:
        # Forecast shorter than the window; extend at the average rather than
        # silently under-ordering.
        lead_time_demand = float(sum(daily)) + average_daily_demand * (
            replenishment_days - len(daily)
        )

    if average_daily_demand > 0:
        stock_cover_days = current_stock / average_daily_demand
    else:
        stock_cover_days = None

    risk = classify_risk(stock_cover_days, lead_time_days, settings)
    overstock = (
        stock_cover_days is None and current_stock > 0
    ) or (stock_cover_days is not None and stock_cover_days > settings.overstock_cover_days)

    daily_std = demand_variability(history)
    buffer = safety_stock(daily_std, replenishment_days, settings)
    target_stock = lead_time_demand + buffer
    reorder_quantity = max(0, int(round(target_stock - current_stock)))

    # Never recommend restocking something already sitting on months of cover.
    if overstock:
        reorder_quantity = 0

    return {
        "product_id": product["id"],
        "sku": product["sku"],
        "name": product["name"],
        "category": product["category"],
        "current_stock": current_stock,
        "reorder_level": int(product["reorder_level"]),
        "lead_time_days": lead_time_days,
        "expected_7_day_demand": round(expected_7_day_demand, 1),
        "average_daily_demand": round(average_daily_demand, 2),
        "stock_cover_days": round(stock_cover_days, 1) if stock_cover_days is not None else None,
        "risk": risk,
        "overstock": overstock,
        "demand_std_dev": round(daily_std, 2),
        "safety_stock": round(buffer, 1),
        "target_stock": round(target_stock, 1),
        "recommended_reorder_quantity": reorder_quantity,
        "reason": build_reason(risk, overstock, stock_cover_days, lead_time_days, reorder_quantity),
    }


def analyse_product(product_id: int) -> dict[str, Any] | None:
    """Inventory assessment for one product id, or None when unknown."""
    product = product_model.get_product(product_id)
    if product is None:
        return None

    settings = get_settings()
    horizon = max(7, int(product["lead_time_days"]) + settings.safety_days)

    history = sale_model.daily_history(product_id)
    if not history:
        raise InsufficientHistoryError(f"Product {product_id} has no sales history")

    forecast_rows = forecast_service.forecast_product(product, days=horizon, history=history)
    return analyse(product, history, forecast_rows, settings)


def recommendations(risk_filter: str | None = None) -> list[dict[str, Any]]:
    """Assess the whole catalogue, most urgent first.

    Products without enough history are skipped rather than failing the request.
    """
    settings = get_settings()
    products = product_model.list_products(limit=1000)

    results: list[dict[str, Any]] = []
    for product in products:
        history = sale_model.daily_history(product["id"])
        if not history:
            continue

        horizon = max(7, int(product["lead_time_days"]) + settings.safety_days)
        try:
            forecast_rows = forecast_service.forecast_product(
                product, days=horizon, history=history
            )
        except (InsufficientHistoryError, ModelNotTrainedError) as exc:
            logger.info("Skipping product %s: %s", product["id"], exc)
            continue

        results.append(analyse(product, history, forecast_rows, settings))

    if risk_filter:
        results = [row for row in results if row["risk"] == risk_filter]

    # Highest risk first, then whichever will run out soonest.
    results.sort(
        key=lambda row: (
            -RISK_ORDER[row["risk"]],
            row["stock_cover_days"] if row["stock_cover_days"] is not None else float("inf"),
        )
    )
    return results


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Headline counts for the dashboard cards."""
    return {
        "total_products": len(rows),
        "critical_products": sum(1 for r in rows if r["risk"] == "CRITICAL"),
        "high_risk_products": sum(1 for r in rows if r["risk"] == "HIGH"),
        "medium_risk_products": sum(1 for r in rows if r["risk"] == "MEDIUM"),
        "low_risk_products": sum(1 for r in rows if r["risk"] == "LOW"),
        "overstocked_products": sum(1 for r in rows if r["overstock"]),
        "expected_7_day_units": round(sum(r["expected_7_day_demand"] for r in rows), 1),
        "total_reorder_units": sum(r["recommended_reorder_quantity"] for r in rows),
    }
