"""Inventory: the ledger, adjustments, stock position and reorder advice.

The forecast-driven tests (risk classification, safety stock, reorder
quantities) exercise pure functions with fabricated inputs, so they run without
a trained model. The endpoint tests that need real forecasts use the seeded demo
store and skip when it is absent.
"""

from __future__ import annotations

import math

import pytest

from app.services.inventory_service import (
    build_reason,
    classify_risk,
    demand_variability,
    safety_stock,
    summarise,
)
from app.services.policy import StorePolicy

POLICY = StorePolicy(
    critical_cover_days=2.0,
    medium_cover_buffer_days=3.0,
    overstock_cover_days=30.0,
    safety_days=3,
    service_level_z=1.28,
    low_stock_threshold=10,
    anomaly_recent_days=7,
    anomaly_baseline_days=28,
    anomaly_min_change=0.25,
    anomaly_min_zscore=2.0,
    slow_moving_threshold=0.25,
)


# --------------------------------------------------------------------------
# Risk classification
# --------------------------------------------------------------------------


def test_very_low_cover_is_critical():
    assert classify_risk(1.0, lead_time_days=2, settings=POLICY) == "CRITICAL"


def test_cover_inside_the_lead_time_is_high_risk():
    """Four days of stock with a seven-day supplier will run out."""
    assert classify_risk(4.0, lead_time_days=7, settings=POLICY) == "HIGH"


def test_cover_just_past_the_lead_time_is_medium():
    assert classify_risk(8.0, lead_time_days=7, settings=POLICY) == "MEDIUM"


def test_comfortable_cover_is_low_risk():
    assert classify_risk(20.0, lead_time_days=3, settings=POLICY) == "LOW"


def test_risk_is_relative_to_lead_time():
    """The same cover is far more dangerous with a slow supplier than a fast one."""
    assert classify_risk(3.0, lead_time_days=1, settings=POLICY) == "MEDIUM"
    assert classify_risk(3.0, lead_time_days=7, settings=POLICY) == "HIGH"
    assert classify_risk(10.0, lead_time_days=1, settings=POLICY) == "LOW"


def test_no_predicted_demand_is_not_a_stockout_risk():
    assert classify_risk(None, lead_time_days=5, settings=POLICY) == "LOW"


# --------------------------------------------------------------------------
# Safety stock
# --------------------------------------------------------------------------


def test_safety_stock_follows_the_square_root_of_time():
    """Forecast error accumulates with sqrt(days), not linearly."""
    one_day = safety_stock(10.0, 1, POLICY)
    nine_days = safety_stock(10.0, 9, POLICY)
    assert nine_days == pytest.approx(one_day * 3.0)


def test_steady_demand_needs_no_buffer():
    assert safety_stock(0.0, 7, POLICY) == 0.0


def test_erratic_demand_needs_a_bigger_buffer():
    assert safety_stock(20.0, 7, POLICY) > safety_stock(5.0, 7, POLICY)


def test_demand_variability_counts_zero_sale_days():
    """A day with no sales is a real zero; dropping it understates volatility."""
    from datetime import date, timedelta

    start = date(2026, 6, 1)
    sparse = [
        {"sale_date": start + timedelta(days=i), "quantity": q}
        for i, q in enumerate([10, 0, 10, 0, 10, 0, 10])
    ]
    assert demand_variability(sparse) > 4.0


# --------------------------------------------------------------------------
# Explanations
# --------------------------------------------------------------------------


def test_critical_reason_names_the_quantity_and_the_lead_time():
    reason = build_reason("CRITICAL", False, 1.0, 4, 60)
    assert "60 units" in reason
    assert "4" in reason


def test_overstock_reason_advises_against_reordering():
    reason = build_reason("LOW", True, 90.0, 3, 0)
    assert "hold off" in reason.lower()


def test_no_demand_reason_is_explicit():
    reason = build_reason("LOW", False, None, 3, 0)
    assert "No demand predicted" in reason


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------


def test_summarise_counts_each_risk_level():
    rows = [
        {"risk": "CRITICAL", "overstock": False, "expected_7_day_demand": 10.0,
         "recommended_reorder_quantity": 5},
        {"risk": "CRITICAL", "overstock": False, "expected_7_day_demand": 4.0,
         "recommended_reorder_quantity": 2},
        {"risk": "LOW", "overstock": True, "expected_7_day_demand": 1.0,
         "recommended_reorder_quantity": 0},
    ]
    summary = summarise(rows)
    assert summary["total_products"] == 3
    assert summary["critical_products"] == 2
    assert summary["overstocked_products"] == 1
    assert summary["total_reorder_units"] == 7
    assert summary["expected_7_day_units"] == 15.0


# --------------------------------------------------------------------------
# The ledger
# --------------------------------------------------------------------------


def test_adjustment_reduces_stock_and_records_the_reason(client, headers, product):
    response = client.post(
        "/inventory/adjustments",
        headers=headers,
        json={
            "product_id": product["id"],
            "quantity_change": -8,
            "reason": "DAMAGE",
            "notes": "Crushed in transit",
        },
    )
    assert response.status_code == 201, response.text

    movement = response.json()
    assert movement["type"] == "DAMAGE"
    assert movement["quantity_change"] == -8
    assert movement["quantity_after"] == 92
    assert movement["notes"] == "Crushed in transit"

    assert client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"] == 92


def test_adjustment_can_increase_stock(client, headers, product):
    client.post(
        "/inventory/adjustments",
        headers=headers,
        json={"product_id": product["id"], "quantity_change": 25, "reason": "COUNT_CORRECTION"},
    )
    assert client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"] == 125


def test_stock_cannot_be_driven_negative(client, headers, product):
    response = client.post(
        "/inventory/adjustments",
        headers=headers,
        json={"product_id": product["id"], "quantity_change": -500, "reason": "DAMAGE"},
    )
    assert response.status_code == 422
    assert client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"] == 100


def test_zero_adjustment_is_rejected(client, headers, product):
    response = client.post(
        "/inventory/adjustments",
        headers=headers,
        json={"product_id": product["id"], "quantity_change": 0, "reason": "OTHER"},
    )
    assert response.status_code == 422


def test_unknown_adjustment_reason_is_rejected(client, headers, product):
    response = client.post(
        "/inventory/adjustments",
        headers=headers,
        json={"product_id": product["id"], "quantity_change": -1, "reason": "BECAUSE"},
    )
    assert response.status_code == 422


def test_expiry_and_loss_are_recorded_as_damage(client, headers, product):
    """Distinct business reasons, one ledger type — the note carries the detail."""
    for reason in ("EXPIRED", "LOST"):
        response = client.post(
            "/inventory/adjustments",
            headers=headers,
            json={"product_id": product["id"], "quantity_change": -1, "reason": reason},
        )
        assert response.json()["type"] == "DAMAGE"


def test_movements_can_be_filtered_by_type(client, headers, product):
    client.post(
        "/pos/checkout",
        headers=headers,
        json={"items": [{"product_id": product["id"], "quantity": 2}]},
    )
    client.post(
        "/inventory/adjustments",
        headers=headers,
        json={"product_id": product["id"], "quantity_change": -1, "reason": "DAMAGE"},
    )

    sales = client.get("/inventory/movements", headers=headers, params={"type": "SALE"}).json()
    assert sales["total"] == 1
    assert sales["items"][0]["type"] == "SALE"


def test_movements_name_the_person_who_made_them(client, headers, product, store):
    client.post(
        "/inventory/adjustments",
        headers=headers,
        json={"product_id": product["id"], "quantity_change": -1, "reason": "DAMAGE"},
    )
    movement = client.get("/inventory/movements", headers=headers).json()["items"][0]
    assert movement["created_by_name"] == store["owner"]["user"]["full_name"]


# --------------------------------------------------------------------------
# Stock position
# --------------------------------------------------------------------------


def test_stock_position_classifies_every_product(client, headers, product_factory):
    product_factory(current_stock=0, reorder_level=10)
    product_factory(current_stock=5, reorder_level=10)
    product_factory(current_stock=80, reorder_level=10)

    position = client.get("/inventory", headers=headers).json()
    statuses = {row["stock_status"] for row in position["products"]}
    assert statuses == {"OUT_OF_STOCK", "LOW", "OK"}
    assert position["out_of_stock"] == 1
    assert position["low_stock"] == 1


def test_stock_position_values_inventory_at_cost(client, headers, product_factory):
    product_factory(current_stock=10, cost_price="30.00", selling_price="50.00")
    position = client.get("/inventory", headers=headers).json()
    assert position["inventory_cost_value"] == 300.0
    assert position["inventory_retail_value"] == 500.0


def test_stock_position_works_without_a_trained_model(client, headers, product):
    """What is on the shelves is a fact, not a prediction."""
    assert client.get("/inventory", headers=headers).status_code == 200


def test_products_without_history_are_skipped_not_fatal(client, headers, product):
    """A newly added SKU has nothing to forecast; it must not break the request."""
    response = client.get("/inventory/recommendations", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


# --------------------------------------------------------------------------
# Recommendations against real forecasts
# --------------------------------------------------------------------------


def test_recommendations_are_ordered_by_urgency(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers).json()
    if not rows:
        pytest.skip("demo store has no forecastable products")

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ranks = [order[row["risk"]] for row in rows]
    assert ranks == sorted(ranks)


def test_every_recommendation_explains_itself(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers).json()
    if not rows:
        pytest.skip("demo store has no forecastable products")
    assert all(len(row["reason"]) > 20 for row in rows)


def test_recommendations_never_suggest_negative_quantities(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers).json()
    assert all(row["recommended_reorder_quantity"] >= 0 for row in rows)


def test_overstocked_products_are_not_reordered(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers).json()
    assert all(
        row["recommended_reorder_quantity"] == 0 for row in rows if row["overstock"]
    )


def test_risk_filter_returns_only_that_level(client, demo_headers):
    rows = client.get(
        "/inventory/recommendations", headers=demo_headers, params={"risk": "CRITICAL"}
    ).json()
    assert all(row["risk"] == "CRITICAL" for row in rows)


def test_an_invalid_risk_filter_is_rejected(client, demo_headers):
    response = client.get(
        "/inventory/recommendations", headers=demo_headers, params={"risk": "EXTREME"}
    )
    assert response.status_code == 422


def test_summary_matches_the_recommendation_list(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers).json()
    summary = client.get("/inventory/summary", headers=demo_headers).json()
    assert summary["total_products"] == len(rows)
    assert summary["critical_products"] == sum(1 for r in rows if r["risk"] == "CRITICAL")
