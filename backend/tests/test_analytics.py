"""Analytics and anomaly detection tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.config import Settings
from app.models import product as product_model
from app.services.analytics_service import (
    category_trends,
    detect_anomaly,
    slow_moving,
    top_products,
)

SETTINGS = Settings()

PRODUCT = {
    "id": 1,
    "sku": "BEV-001",
    "name": "Cold Drink 1L",
    "category": "Beverages",
}


def series(values: list[float], start: date = date(2026, 6, 1)) -> list[dict]:
    return [
        {"sale_date": start + timedelta(days=i), "quantity": value}
        for i, value in enumerate(values)
    ]


def steady(value: float, days: int) -> list[float]:
    """Mild alternation so the baseline has non-zero variance."""
    return [value + (1 if i % 2 else -1) for i in range(days)]


# --------------------------------------------------------------------------
# Anomaly detection
# --------------------------------------------------------------------------


def test_stable_demand_is_not_an_anomaly():
    history = series(steady(20, 35))
    assert detect_anomaly(history, PRODUCT, SETTINGS) is None


def test_large_spike_is_detected():
    history = series(steady(20, 28) + [35] * 7)
    anomaly = detect_anomaly(history, PRODUCT, SETTINGS)

    assert anomaly is not None
    assert anomaly["direction"] == "SPIKE"
    assert anomaly["change_pct"] > 25


def test_large_drop_is_detected():
    history = series(steady(40, 28) + [12] * 7)
    anomaly = detect_anomaly(history, PRODUCT, SETTINGS)

    assert anomaly is not None
    assert anomaly["direction"] == "DROP"
    assert anomaly["change_pct"] < 0


def test_message_reads_like_the_specification():
    history = series(steady(20, 28) + [33] * 7)
    message = detect_anomaly(history, PRODUCT, SETTINGS)["message"]
    assert message.startswith("Cold Drink 1L demand increased")
    assert "%" in message and "recent average" in message


def test_small_change_is_ignored_even_when_statistically_clear():
    """A rock-steady product moving 10% is significant but not interesting."""
    history = series([20.0] * 28 + [22.0] * 7)
    assert detect_anomaly(history, PRODUCT, SETTINGS) is None


def test_noisy_product_needs_a_bigger_move():
    """The same 40% jump is an anomaly for a steady seller, not for an erratic one."""
    steady_history = series(steady(20, 28) + [28] * 7)
    erratic_history = series([2, 40, 5, 35, 1, 38, 4] * 4 + [28] * 7)

    assert detect_anomaly(steady_history, PRODUCT, SETTINGS) is not None
    assert detect_anomaly(erratic_history, PRODUCT, SETTINGS) is None


def test_thresholds_are_configurable():
    history = series([20.0] * 28 + [22.0] * 7)
    sensitive = Settings(anomaly_min_change=0.05, anomaly_min_zscore=0.5)
    assert detect_anomaly(history, PRODUCT, sensitive) is not None


def test_short_history_yields_no_anomaly():
    assert detect_anomaly(series([10] * 10), PRODUCT, SETTINGS) is None


def test_empty_history_yields_no_anomaly():
    assert detect_anomaly([], PRODUCT, SETTINGS) is None


def test_product_that_never_sells_is_not_an_anomaly():
    assert detect_anomaly(series([0] * 40), PRODUCT, SETTINGS) is None


def test_sales_starting_from_zero_baseline_are_reported_without_a_percentage():
    """Percentage change against zero is undefined, but the jump is still news."""
    history = series([0] * 28 + [15] * 7)
    anomaly = detect_anomaly(history, PRODUCT, SETTINGS)

    assert anomaly is not None
    assert anomaly["change_pct"] is None
    assert "after selling nothing" in anomaly["message"]


def test_anomaly_reports_both_windows():
    history = series(steady(20, 28) + [35] * 7)
    anomaly = detect_anomaly(history, PRODUCT, SETTINGS)

    assert anomaly["recent_days"] == SETTINGS.anomaly_recent_days
    assert anomaly["baseline_days"] == SETTINGS.anomaly_baseline_days
    assert anomaly["recent_daily_average"] == pytest.approx(35.0)


def test_missing_days_count_as_zero_demand():
    """A product that stopped selling entirely should read as a drop."""
    history = [
        {"sale_date": date(2026, 6, 1) + timedelta(days=i), "quantity": 30}
        for i in range(28)
    ]
    # No rows at all for the final week: real zeros, not missing data.
    history.append({"sale_date": date(2026, 7, 5), "quantity": 0})
    anomaly = detect_anomaly(history, PRODUCT, SETTINGS)
    assert anomaly is not None
    assert anomaly["direction"] == "DROP"


# --------------------------------------------------------------------------
# Movers and trends (require the seeded database)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seeded(demo_store_id):
    if not product_model.list_products(demo_store_id, limit=1):
        pytest.skip("no demo store; run scripts/seed_demo.py")


def test_top_products_are_ordered_by_units(seeded, demo_store_id):
    rows = top_products(demo_store_id, limit=5)
    units = [row["total_units"] for row in rows]
    assert units == sorted(units, reverse=True)


def test_top_products_respects_limit(seeded, demo_store_id):
    assert len(top_products(demo_store_id, limit=3)) <= 3


def test_top_products_report_revenue(seeded, demo_store_id):
    assert all(row["total_revenue"] > 0 for row in top_products(demo_store_id, limit=5))


def test_slow_movers_sell_less_than_top_sellers(seeded, demo_store_id):
    fastest = top_products(demo_store_id, limit=1)
    slowest = slow_moving(demo_store_id, limit=1)
    if not slowest:
        pytest.skip("no slow movers in this dataset")
    assert slowest[0]["total_units"] < fastest[0]["total_units"]


def test_category_trends_cover_every_category(seeded, demo_store_id):
    trends = category_trends(demo_store_id)
    categories = {row["category"] for row in trends}
    assert categories == set(product_model.list_categories(demo_store_id))


def test_category_trend_direction_matches_the_numbers(seeded, demo_store_id):
    for row in category_trends(demo_store_id):
        if row["direction"] == "UP":
            assert row["current_units"] > row["previous_units"]
        elif row["direction"] == "DOWN":
            assert row["current_units"] < row["previous_units"]
        else:
            assert row["current_units"] == row["previous_units"]


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


def test_overview_returns_every_documented_field(client, seeded, demo_headers):
    body = client.get("/analytics/overview", headers=demo_headers).json()
    expected = {
        "total_products", "critical_products", "high_risk_products",
        "medium_risk_products", "low_risk_products", "overstocked_products",
        "expected_7_day_units", "total_reorder_units", "anomaly_count",
        "anomalies", "top_reorders",
    }
    assert expected == set(body)


def test_overview_anomaly_limit_is_respected(client, seeded, demo_headers):
    body = client.get("/analytics/overview", headers=demo_headers, params={"anomaly_limit": 2}).json()
    assert len(body["anomalies"]) <= 2
    # The count is the full total, not the truncated list.
    assert body["anomaly_count"] >= len(body["anomalies"])


def test_anomalies_endpoint_sorts_by_deviation(client, seeded, demo_headers):
    rows = client.get("/analytics/anomalies", headers=demo_headers).json()
    scores = [abs(row["z_score"]) for row in rows if row["z_score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_every_anomaly_carries_a_readable_message(client, seeded, demo_headers):
    rows = client.get("/analytics/anomalies", headers=demo_headers).json()
    assert all(len(row["message"]) > 20 for row in rows)


@pytest.mark.parametrize(
    "path,params",
    [
        ("/analytics/top-products", {"days": 3}),
        ("/analytics/top-products", {"limit": 0}),
        ("/analytics/slow-moving", {"days": 500}),
        ("/analytics/category-trends", {"days": 999}),
        ("/analytics/overview", {"anomaly_limit": 0}),
        ("/analytics/anomalies", {"limit": 200}),
    ],
)
def test_invalid_analytics_parameters_are_rejected(client, demo_headers, path, params):
    assert client.get(path, headers=demo_headers, params=params).status_code == 422
