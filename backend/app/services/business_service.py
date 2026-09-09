"""Business analytics: the dashboard, the briefing, profit and reports.

Two rules run through this module.

Metrics are labelled for what they actually are. Revenue minus cost of goods is
gross profit, not profit; subtract recorded expenses and it becomes an
*estimate* of operating profit, because a shop's real costs include things
nobody typed into the expenses screen.

Nothing here invents a number. When there is no data, the figure is zero or
absent and the UI says so — a dashboard that guesses is worse than an empty one.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from app.errors import ValidationError
from app.ml.predict import ModelNotTrainedError
from app.models import expense as expense_model
from app.models import product as product_model
from app.models import sale as sale_model
from app.services import analytics_service, inventory_service

logger = logging.getLogger(__name__)

PERIODS = {"today": 0, "7d": 6, "30d": 29, "90d": 89, "365d": 364}


def resolve_period(period: str, start: date | None, end: date | None) -> tuple[date, date]:
    """Turn a period name or explicit dates into an inclusive range."""
    if start and end:
        if start > end:
            raise ValidationError("start_date must not be after end_date")
        return start, end
    if period not in PERIODS:
        raise ValidationError(f"period must be one of {list(PERIODS)}")

    today = date.today()
    return today - timedelta(days=PERIODS[period]), today


def _profit_block(kpis: dict[str, Any]) -> dict[str, Any]:
    """Revenue, COGS and gross profit, with the margin only when it is defined."""
    revenue = float(kpis["revenue"])
    tax = float(kpis["tax"])
    cost = float(kpis["cost_of_goods"])
    net_revenue = revenue - tax
    gross_profit = net_revenue - cost

    return {
        "revenue": round(revenue, 2),
        "tax": round(tax, 2),
        "net_revenue": round(net_revenue, 2),
        "cost_of_goods": round(cost, 2),
        "gross_profit": round(gross_profit, 2),
        # A margin on zero revenue is not 0%, it is undefined.
        "gross_margin_pct": round(gross_profit / net_revenue * 100, 1) if net_revenue else None,
    }


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------


def dashboard(store_id: int) -> dict[str, Any]:
    """Everything the overview screen needs, in one request.

    Forecast-derived sections degrade independently: a store with no trained
    model still sees its revenue, stock and best sellers.
    """
    today = date.today()
    week_ago = today - timedelta(days=6)

    today_kpis = sale_model.kpis(store_id, today, today)
    week_kpis = sale_model.kpis(store_id, week_ago, today)
    yesterday_kpis = sale_model.kpis(store_id, today - timedelta(days=1), today - timedelta(days=1))
    catalogue = product_model.catalogue_stats(store_id)

    recommendations: list[dict[str, Any]] = []
    inventory_summary: dict[str, Any] | None = None
    anomalies: list[dict[str, Any]] = []
    forecast_available = True

    try:
        recommendations = inventory_service.recommendations(store_id)
        inventory_summary = inventory_service.summarise(recommendations)
        anomalies = analytics_service.detect_anomalies(store_id, limit=5)
    except ModelNotTrainedError:
        forecast_available = False

    return {
        "date": today.isoformat(),
        "today": {
            **_profit_block(today_kpis),
            "orders": int(today_kpis["orders"]),
            "units": int(today_kpis["units"]),
            "average_order_value": round(float(today_kpis["average_order_value"]), 2),
        },
        "yesterday_revenue": round(float(yesterday_kpis["revenue"]), 2),
        "week": {
            **_profit_block(week_kpis),
            "orders": int(week_kpis["orders"]),
            "units": int(week_kpis["units"]),
        },
        "inventory": {
            "total_products": int(catalogue["total"]),
            "low_stock": int(catalogue["low_stock"]),
            "out_of_stock": int(catalogue["out_of_stock"]),
            "inventory_cost_value": round(float(catalogue["inventory_cost_value"]), 2),
            "inventory_retail_value": round(float(catalogue["inventory_retail_value"]), 2),
        },
        "forecast_available": forecast_available,
        "risk": inventory_summary,
        "reorders": [
            row for row in recommendations if row["recommended_reorder_quantity"] > 0
        ][:5],
        "anomalies": anomalies,
        "top_products": analytics_service.top_products(store_id, days=30, limit=5),
        "slow_movers": analytics_service.slow_moving(store_id, days=30, limit=5),
        "recent_sales": sale_model.recent_sales(store_id, limit=8),
        "revenue_series": sale_model.revenue_series(store_id, week_ago, today),
    }


def briefing(store_id: int, user_name: str) -> dict[str, Any]:
    """The command-centre summary: what needs attention, and what to do about it.

    Every line is derived from a real number and says why it is there. Nothing
    is described as an AI insight — it is a forecast, a stock level, or a count.
    """
    from app.models import purchase as purchase_model

    today = date.today()
    today_kpis = sale_model.kpis(store_id, today, today)
    catalogue = product_model.catalogue_stats(store_id)
    open_orders = purchase_model.count_orders(store_id, status="ORDERED")

    headlines: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    if int(catalogue["out_of_stock"]):
        headlines.append({
            "icon": "stock",
            "text": f"{catalogue['out_of_stock']} product(s) are out of stock",
            "link": "/inventory?status=out",
        })
    if int(catalogue["low_stock"]):
        headlines.append({
            "icon": "stock",
            "text": f"{catalogue['low_stock']} product(s) are at or below their reorder level",
            "link": "/inventory?status=low",
        })
    if open_orders:
        headlines.append({
            "icon": "purchase",
            "text": f"{open_orders} purchase order(s) awaiting delivery",
            "link": "/purchases?status=ORDERED",
        })

    try:
        recommendations = inventory_service.recommendations(store_id)
        urgent = [
            row
            for row in recommendations
            if row["risk"] in ("CRITICAL", "HIGH") and row["recommended_reorder_quantity"] > 0
        ]
        for row in urgent[:3]:
            cover = row["stock_cover_days"]
            when = (
                "less than a day" if cover is not None and cover < 1
                else f"about {cover:.0f} days" if cover is not None
                else "an unknown time"
            )
            actions.append({
                "kind": "REORDER",
                "product_id": row["product_id"],
                "title": f"Reorder {row['name']}",
                "detail": (
                    f"{row['current_stock']} left, {when} of cover, and the supplier "
                    f"takes {row['lead_time_days']} days. "
                    f"Suggested order: {row['recommended_reorder_quantity']} units."
                ),
                "link": "/purchases/new",
            })

        anomalies = analytics_service.detect_anomalies(store_id, limit=2)
        for anomaly in anomalies:
            headlines.append({
                "icon": "trend",
                "text": anomaly["message"],
                "link": f"/forecasting?product={anomaly['product_id']}",
            })
            if anomaly["direction"] == "DROP":
                actions.append({
                    "kind": "INVESTIGATE",
                    "product_id": anomaly["product_id"],
                    "title": f"Check {anomaly['name']}",
                    "detail": anomaly["message"],
                    "link": f"/forecasting?product={anomaly['product_id']}",
                })
    except ModelNotTrainedError:
        actions.append({
            "kind": "TRAIN",
            "title": "Train the demand model",
            "detail": (
                "Forecasts and reorder advice unlock once the model has been trained "
                "on this store's sales."
            ),
            "link": "/forecasting",
        })

    revenue = round(float(today_kpis["revenue"]), 2)
    headlines.insert(0, {
        "icon": "revenue",
        "text": (
            f"Today's revenue is {revenue:,.2f} across {int(today_kpis['orders'])} sale(s)"
            if today_kpis["orders"]
            else "No sales recorded yet today"
        ),
        "link": "/sales",
    })

    return {
        "greeting": _greeting(),
        "user_name": user_name,
        "attention_count": len(headlines) - 1,
        "headlines": headlines,
        "actions": actions,
        "today_revenue": revenue,
        "today_orders": int(today_kpis["orders"]),
    }


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


# --------------------------------------------------------------------------
# Analytics
# --------------------------------------------------------------------------


def sales_analytics(store_id: int, start: date, end: date) -> dict[str, Any]:
    kpis = sale_model.kpis(store_id, start, end)
    days = (end - start).days + 1

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": days,
        **_profit_block(kpis),
        "orders": int(kpis["orders"]),
        "units": int(kpis["units"]),
        "discount": round(float(kpis["discount"]), 2),
        "average_order_value": round(float(kpis["average_order_value"]), 2),
        "daily_average_revenue": round(float(kpis["revenue"]) / days, 2) if days else 0,
        "series": sale_model.revenue_series(store_id, start, end),
        "payment_split": [
            {
                "payment_method": row["payment_method"],
                "orders": int(row["orders"]),
                "revenue": round(float(row["revenue"]), 2),
            }
            for row in sale_model.payment_split(store_id, start, end)
        ],
    }


def product_analytics(store_id: int, start: date, end: date, limit: int = 10) -> dict[str, Any]:
    rows = [
        {
            "product_id": int(row["product_id"]),
            "sku": row["sku"],
            "name": row["name"],
            "category": row["category"],
            "current_stock": int(row["current_stock"]),
            "total_units": int(row["total_units"]),
            "total_revenue": round(float(row["total_revenue"]), 2),
            "total_cost": round(float(row["total_cost"]), 2),
            "gross_profit": round(float(row["gross_profit"]), 2),
        }
        for row in sale_model.product_performance(store_id, start, end)
    ]

    sold = [row for row in rows if row["total_units"] > 0]
    return {
        "best_sellers": sorted(sold, key=lambda r: r["total_units"], reverse=True)[:limit],
        "most_profitable": sorted(sold, key=lambda r: r["gross_profit"], reverse=True)[:limit],
        "worst_sellers": sorted(sold, key=lambda r: r["total_units"])[:limit],
        # Distinguished from "sold a little": these sold nothing at all.
        "no_sales": [row for row in rows if row["total_units"] == 0][:limit],
    }


def inventory_analytics(store_id: int, start: date, end: date) -> dict[str, Any]:
    """Valuation, turnover and dead stock.

    Turnover uses cost of goods over average inventory at cost, which is the
    standard definition; using retail value on top would inflate it.
    """
    catalogue = product_model.catalogue_stats(store_id)
    kpis = sale_model.kpis(store_id, start, end)
    performance = sale_model.product_performance(store_id, start, end)

    inventory_value = float(catalogue["inventory_cost_value"])
    cost_of_goods = float(kpis["cost_of_goods"])
    turnover = round(cost_of_goods / inventory_value, 2) if inventory_value else None

    dead_stock = [
        {
            "product_id": int(row["product_id"]),
            "sku": row["sku"],
            "name": row["name"],
            "category": row["category"],
            "current_stock": int(row["current_stock"]),
            "stock_value": round(float(row["current_stock"]) * float(row["cost_price"]), 2),
        }
        for row in performance
        if int(row["total_units"]) == 0 and int(row["current_stock"]) > 0
    ]

    overstock: list[dict[str, Any]] = []
    try:
        overstock = [row for row in inventory_service.recommendations(store_id) if row["overstock"]]
    except ModelNotTrainedError:
        logger.info("Overstock needs a trained model; skipping for store %s", store_id)

    return {
        "inventory_cost_value": round(inventory_value, 2),
        "inventory_retail_value": round(float(catalogue["inventory_retail_value"]), 2),
        "total_products": int(catalogue["total"]),
        "low_stock": int(catalogue["low_stock"]),
        "out_of_stock": int(catalogue["out_of_stock"]),
        "stock_turnover": turnover,
        "cost_of_goods": round(cost_of_goods, 2),
        "dead_stock": sorted(dead_stock, key=lambda r: r["stock_value"], reverse=True)[:20],
        "dead_stock_value": round(sum(row["stock_value"] for row in dead_stock), 2),
        "overstock": overstock[:20],
    }


def category_analytics(store_id: int, days: int = 30) -> list[dict[str, Any]]:
    trends = analytics_service.category_trends(store_id, days=days)
    total = sum(row["current_revenue"] for row in trends)
    return [
        {
            **row,
            "contribution_pct": round(row["current_revenue"] / total * 100, 1) if total else None,
        }
        for row in trends
    ]


def profit_summary(store_id: int, start: date, end: date) -> dict[str, Any]:
    """Gross profit from sales, then an estimate of operating profit.

    Labelled carefully on purpose: expenses here are only the ones somebody
    recorded, so what comes out is an estimate, not an accounting result.
    """
    kpis = sale_model.kpis(store_id, start, end)
    block = _profit_block(kpis)
    expenses = expense_model.total_amount(store_id, start, end)
    estimated_operating_profit = block["gross_profit"] - expenses

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        **block,
        "orders": int(kpis["orders"]),
        "recorded_expenses": round(expenses, 2),
        "expense_breakdown": [
            {
                "category": row["category"],
                "total": round(float(row["total"]), 2),
                "entries": int(row["entries"]),
            }
            for row in expense_model.totals_by_category(store_id, start, end)
        ],
        "estimated_operating_profit": round(estimated_operating_profit, 2),
        "note": (
            "Estimated operating profit is gross profit minus expenses recorded in "
            "Kirana-IQ. It is not a full accounting profit — costs that were never "
            "entered are not subtracted."
        ),
    }
