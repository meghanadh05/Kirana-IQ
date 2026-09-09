"""Forecast and inventory endpoint tests.

These run against the real database and the trained model. When either is
missing the tests skip rather than fail, so a fresh clone can still run the
suite before training.
"""

from __future__ import annotations

import pytest

from app.ml.predict import MODEL_PATH
from app.models import product as product_model

requires_model = pytest.mark.skipif(
    not MODEL_PATH.exists(), reason="no trained model; run python -m app.ml.train_model"
)


@pytest.fixture(scope="module")
def seeded_product_id(demo_store_id) -> int:
    products = product_model.list_products(demo_store_id, limit=1)
    if not products:
        pytest.skip("no demo store; run scripts/seed_demo.py")
    return products[0]["id"]


# --------------------------------------------------------------------------
# Model status
# --------------------------------------------------------------------------


def test_model_endpoint_always_answers(client, demo_headers):
    """Reports untrained rather than erroring when no model exists."""
    response = client.get("/model", headers=demo_headers)
    assert response.status_code == 200
    assert "trained" in response.json()


@requires_model
def test_model_endpoint_reports_metrics(client, demo_headers):
    body = client.get("/model", headers=demo_headers).json()
    assert body["trained"] is True
    assert body["features"] > 0
    assert body["metrics"]


# --------------------------------------------------------------------------
# Forecast
# --------------------------------------------------------------------------


@requires_model
@pytest.mark.parametrize("days", [7, 14, 30])
def test_forecast_supports_every_documented_horizon(client, seeded_product_id, days, demo_headers):
    response = client.get(f"/forecast/{seeded_product_id}", headers=demo_headers, params={"days": days})
    assert response.status_code == 200

    body = response.json()
    assert body["forecast_days"] == days
    assert len(body["forecast"]) == days


@requires_model
def test_forecast_predictions_are_non_negative(client, seeded_product_id, demo_headers):
    body = client.get(f"/forecast/{seeded_product_id}", headers=demo_headers, params={"days": 30}).json()
    assert all(point["predicted_demand"] >= 0 for point in body["forecast"])


@requires_model
def test_forecast_dates_are_strictly_increasing(client, seeded_product_id, demo_headers):
    body = client.get(f"/forecast/{seeded_product_id}", headers=demo_headers, params={"days": 14}).json()
    dates = [point["date"] for point in body["forecast"]]
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)


@requires_model
def test_forecast_starts_after_the_last_observed_day(client, seeded_product_id, demo_headers):
    body = client.get(f"/forecast/{seeded_product_id}", headers=demo_headers, params={"days": 7}).json()
    assert body["forecast"][0]["date"] > body["history"][-1]["date"]


@requires_model
def test_forecast_total_matches_the_daily_rows(client, seeded_product_id, demo_headers):
    body = client.get(f"/forecast/{seeded_product_id}", headers=demo_headers, params={"days": 7}).json()
    assert body["total_predicted_demand"] == sum(p["predicted_demand"] for p in body["forecast"])


@requires_model
def test_forecast_includes_requested_history_window(client, seeded_product_id, demo_headers):
    body = client.get(
        f"/forecast/{seeded_product_id}", headers=demo_headers, params={"days": 7, "history_days": 10}
    ).json()
    assert len(body["history"]) == 10


@pytest.mark.parametrize("days", [0, 1, 5, 9, 31, 100, -7])
def test_forecast_rejects_unsupported_horizons(client, seeded_product_id, days, demo_headers):
    response = client.get(f"/forecast/{seeded_product_id}", headers=demo_headers, params={"days": days})
    assert response.status_code == 422


def test_forecast_rejects_non_numeric_days(client, seeded_product_id, demo_headers):
    assert client.get(f"/forecast/{seeded_product_id}", headers=demo_headers, params={"days": "week"}).status_code == 422


@requires_model
def test_forecast_for_unknown_product_returns_404(client, demo_headers):
    assert client.get("/forecast/99999999", headers=demo_headers, params={"days": 7}).status_code == 404


# --------------------------------------------------------------------------
# Inventory
# --------------------------------------------------------------------------


@requires_model
def test_recommendations_cover_the_catalogue(client, demo_headers):
    response = client.get("/inventory/recommendations", headers=demo_headers)
    assert response.status_code == 200
    assert len(response.json()) > 0


@requires_model
def test_recommendations_are_ordered_most_urgent_first(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers).json()
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ranks = [order[row["risk"]] for row in rows]
    assert ranks == sorted(ranks)


@requires_model
def test_recommendations_never_suggest_negative_quantities(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers).json()
    assert all(row["recommended_reorder_quantity"] >= 0 for row in rows)


@requires_model
def test_every_recommendation_carries_an_explanation(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers).json()
    assert all(len(row["reason"]) > 20 for row in rows)


@requires_model
def test_recommendations_can_be_filtered_by_risk(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers, params={"risk": "LOW"}).json()
    assert all(row["risk"] == "LOW" for row in rows)


def test_invalid_risk_filter_is_rejected(client, demo_headers):
    assert client.get(
        "/inventory/recommendations", headers=demo_headers, params={"risk": "URGENT"}
    ).status_code == 422


@requires_model
def test_summary_totals_agree_with_the_recommendation_list(client, demo_headers):
    rows = client.get("/inventory/recommendations", headers=demo_headers).json()
    summary = client.get("/inventory/summary", headers=demo_headers).json()

    assert summary["total_products"] == len(rows)
    assert summary["critical_products"] == sum(1 for r in rows if r["risk"] == "CRITICAL")
    assert summary["overstocked_products"] == sum(1 for r in rows if r["overstock"])
    assert summary["total_reorder_units"] == sum(
        r["recommended_reorder_quantity"] for r in rows
    )


@requires_model
def test_single_product_recommendation_matches_the_list_entry(client, seeded_product_id, demo_headers):
    single = client.get(f"/inventory/{seeded_product_id}", headers=demo_headers).json()
    listed = next(
        row
        for row in client.get("/inventory/recommendations", headers=demo_headers).json()
        if row["product_id"] == seeded_product_id
    )
    assert single["risk"] == listed["risk"]
    assert single["recommended_reorder_quantity"] == listed["recommended_reorder_quantity"]


@requires_model
def test_inventory_for_unknown_product_returns_404(client, demo_headers):
    assert client.get("/inventory/99999999", headers=demo_headers).status_code == 404


def test_inventory_rejects_non_integer_product_id(client, demo_headers):
    assert client.get("/inventory/not-a-number", headers=demo_headers).status_code == 422
