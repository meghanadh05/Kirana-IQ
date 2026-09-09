"""Inventory intelligence tests.

The maths here decides what a shop owner actually orders, so the thresholds and
formulas are pinned directly rather than only through the API.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from app.config import Settings
from app.services.inventory_service import (
    analyse,
    build_reason,
    classify_risk,
    demand_variability,
    safety_stock,
    summarise,
)

SETTINGS = Settings()

PRODUCT = {
    "id": 1,
    "sku": "DRY-001",
    "name": "Test Milk 1L",
    "category": "Dairy",
    "unit_price": 33.0,
    "current_stock": 40,
    "reorder_level": 20,
    "lead_time_days": 4,
}


def forecast_rows(daily: int = 10, days: int = 10) -> list[dict]:
    return [
        {"date": (date(2026, 9, 9) + timedelta(days=i)).isoformat(), "predicted_demand": daily}
        for i in range(days)
    ]


def history(quantity: int = 10, days: int = 60) -> list[dict]:
    return [
        {"sale_date": date(2026, 7, 1) + timedelta(days=i), "quantity": quantity}
        for i in range(days)
    ]


# --------------------------------------------------------------------------
# Risk classification
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cover,lead_time,expected",
    [
        (0.0, 4, "CRITICAL"),
        (2.0, 4, "CRITICAL"),   # boundary: <= critical_cover_days
        (2.1, 4, "HIGH"),
        (4.0, 4, "HIGH"),       # boundary: <= lead_time
        (4.1, 4, "MEDIUM"),
        (7.0, 4, "MEDIUM"),     # boundary: <= lead_time + buffer
        (7.1, 4, "LOW"),
        (100.0, 4, "LOW"),
    ],
)
def test_risk_ladder_boundaries(cover, lead_time, expected):
    assert classify_risk(cover, lead_time, SETTINGS) == expected


def test_risk_is_relative_to_lead_time():
    """Identical cover, different suppliers: the same 5 days means different risk.

    With a 1-day supplier, 5 days of cover is comfortable. With a 7-day
    supplier, the same 5 days runs out before the delivery arrives.
    """
    assert classify_risk(5.0, 1, SETTINGS) == "LOW"
    assert classify_risk(5.0, 4, SETTINGS) == "MEDIUM"
    assert classify_risk(5.0, 7, SETTINGS) == "HIGH"


def test_critical_wins_even_when_lead_time_is_zero():
    assert classify_risk(1.0, 0, SETTINGS) == "CRITICAL"


def test_no_predicted_demand_is_not_a_stockout_risk():
    assert classify_risk(None, 5, SETTINGS) == "LOW"


def test_thresholds_are_configurable():
    strict = Settings(critical_cover_days=10.0)
    assert classify_risk(8.0, 2, SETTINGS) == "LOW"
    assert classify_risk(8.0, 2, strict) == "CRITICAL"


# --------------------------------------------------------------------------
# Safety stock
# --------------------------------------------------------------------------


def test_safety_stock_scales_with_square_root_of_time():
    """Forecast error accumulates with sqrt(days), not linearly."""
    one_day = safety_stock(5.0, 1, SETTINGS)
    nine_days = safety_stock(5.0, 9, SETTINGS)
    assert nine_days == pytest.approx(one_day * 3.0)


def test_safety_stock_matches_the_formula():
    assert safety_stock(4.0, 9, SETTINGS) == pytest.approx(SETTINGS.service_level_z * 4.0 * 3.0)


def test_steady_demand_needs_no_safety_stock():
    assert safety_stock(0.0, 10, SETTINGS) == 0.0


def test_demand_variability_counts_zero_sale_days():
    """Sparse history must not look artificially steady."""
    sparse = [
        {"sale_date": date(2026, 8, 1), "quantity": 10},
        {"sale_date": date(2026, 8, 5), "quantity": 10},
    ]
    assert demand_variability(sparse) > 0


def test_demand_variability_of_flat_history_is_zero():
    assert demand_variability(history(10)) == pytest.approx(0.0)


def test_demand_variability_handles_empty_history():
    assert demand_variability([]) == 0.0


# --------------------------------------------------------------------------
# Full assessment
# --------------------------------------------------------------------------


def test_stock_cover_is_stock_over_average_daily_demand():
    result = analyse(PRODUCT, history(), forecast_rows(daily=10), SETTINGS)
    assert result["average_daily_demand"] == pytest.approx(10.0)
    assert result["stock_cover_days"] == pytest.approx(4.0)


def test_expected_7_day_demand_sums_only_seven_days():
    result = analyse(PRODUCT, history(), forecast_rows(daily=10, days=30), SETTINGS)
    assert result["expected_7_day_demand"] == 70.0


def test_reorder_covers_lead_time_plus_safety_days():
    """Flat demand, no variability: target is exactly the replenishment window."""
    product = {**PRODUCT, "current_stock": 0, "lead_time_days": 4}
    result = analyse(product, history(10), forecast_rows(daily=10), SETTINGS)

    expected_window = 4 + SETTINGS.safety_days  # 7 days
    assert result["recommended_reorder_quantity"] == 10 * expected_window


def test_reorder_subtracts_stock_already_held():
    product = {**PRODUCT, "current_stock": 30}
    result = analyse(product, history(10), forecast_rows(daily=10), SETTINGS)
    assert result["recommended_reorder_quantity"] == 70 - 30


def test_reorder_is_never_negative():
    product = {**PRODUCT, "current_stock": 10_000}
    result = analyse(product, history(10), forecast_rows(daily=10), SETTINGS)
    assert result["recommended_reorder_quantity"] == 0


def test_overstock_flagged_above_threshold():
    product = {**PRODUCT, "current_stock": 400}  # 40 days at 10/day
    result = analyse(product, history(10), forecast_rows(daily=10), SETTINGS)
    assert result["overstock"] is True
    assert result["risk"] == "LOW"


def test_overstocked_products_are_never_told_to_reorder():
    product = {**PRODUCT, "current_stock": 400}
    assert analyse(product, history(10), forecast_rows(daily=10), SETTINGS)[
        "recommended_reorder_quantity"
    ] == 0


def test_zero_demand_gives_undefined_cover_not_a_crash():
    result = analyse(PRODUCT, history(0), forecast_rows(daily=0), SETTINGS)
    assert result["stock_cover_days"] is None
    assert result["risk"] == "LOW"
    assert result["overstock"] is True  # stock on hand, nothing selling


def test_short_forecast_is_extended_at_the_average():
    """A 7-day forecast must still cover a 10-day replenishment window."""
    product = {**PRODUCT, "current_stock": 0, "lead_time_days": 7}
    result = analyse(product, history(10), forecast_rows(daily=10, days=7), SETTINGS)
    assert result["recommended_reorder_quantity"] == 10 * (7 + SETTINGS.safety_days)


def test_variable_demand_increases_the_reorder_quantity():
    """Two products with identical means but different volatility order differently."""
    steady = analyse(PRODUCT, history(10), forecast_rows(daily=10), SETTINGS)

    erratic_history = [
        {"sale_date": date(2026, 7, 1) + timedelta(days=i), "quantity": 20 if i % 2 else 0}
        for i in range(60)
    ]
    erratic = analyse(PRODUCT, erratic_history, forecast_rows(daily=10), SETTINGS)

    assert erratic["safety_stock"] > steady["safety_stock"]
    assert erratic["recommended_reorder_quantity"] > steady["recommended_reorder_quantity"]


def test_assessment_exposes_every_documented_field():
    result = analyse(PRODUCT, history(), forecast_rows(), SETTINGS)
    expected = {
        "product_id", "sku", "name", "category", "current_stock", "reorder_level",
        "lead_time_days", "expected_7_day_demand", "average_daily_demand",
        "stock_cover_days", "risk", "overstock", "demand_std_dev", "safety_stock",
        "target_stock", "recommended_reorder_quantity", "reason",
    }
    assert expected == set(result)


# --------------------------------------------------------------------------
# Explanations and summary
# --------------------------------------------------------------------------


def test_reason_explains_the_lead_time_conflict():
    reason = build_reason("HIGH", False, 2.5, 5, 35)
    assert "5" in reason and "35" in reason
    assert "run out" in reason.lower()


def test_reason_for_overstock_advises_against_reordering():
    reason = build_reason("LOW", True, 45.0, 3, 0)
    assert "hold off" in reason.lower() or "tied up" in reason.lower()


def test_reason_handles_undefined_cover():
    assert "no demand" in build_reason("LOW", True, None, 3, 0).lower()


def test_summary_counts_each_risk_level():
    rows = [
        {"risk": "CRITICAL", "overstock": False, "expected_7_day_demand": 10, "recommended_reorder_quantity": 5},
        {"risk": "HIGH", "overstock": False, "expected_7_day_demand": 20, "recommended_reorder_quantity": 7},
        {"risk": "LOW", "overstock": True, "expected_7_day_demand": 5, "recommended_reorder_quantity": 0},
    ]
    summary = summarise(rows)
    assert summary["total_products"] == 3
    assert summary["critical_products"] == 1
    assert summary["high_risk_products"] == 1
    assert summary["overstocked_products"] == 1
    assert summary["expected_7_day_units"] == 35
    assert summary["total_reorder_units"] == 12
