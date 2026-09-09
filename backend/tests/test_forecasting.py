"""Metric and forecasting tests.

Forecast tests use a stub model rather than the trained artefact, so they run
in CI without first training and they isolate the forecasting *mechanics* from
model quality.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from app.ml.evaluate import (
    comparison_table,
    evaluate,
    flat_baseline_forecast,
    mae,
    moving_average_baseline,
    rmse,
    wape,
)
from app.ml.feature_engineering import FEATURE_COLUMNS, build_features
from app.ml.predict import (
    InsufficientHistoryError,
    forecast,
    forecast_units,
)

PRODUCT = {
    "id": 1,
    "sku": "TEST-001",
    "name": "Test Milk 1L",
    "category": "Dairy",
    "unit_price": 33.0,
}


class ConstantModel:
    """Stub regressor that always predicts the same value."""

    def __init__(self, value: float):
        self.value = value

    def predict(self, features):
        return np.full(len(features), self.value)


def bundle(value: float = 12.0) -> dict:
    return {
        "model": ConstantModel(value),
        "feature_columns": FEATURE_COLUMNS,
        "model_name": "ConstantStub",
        "trained_at": "2026-09-08T00:00:00+00:00",
        "metrics": {},
    }


def make_history(days: int = 120, start: date = date(2026, 1, 1)) -> list[dict]:
    return [
        {"sale_date": start + timedelta(days=i), "quantity": 20, "avg_price": 33.0}
        for i in range(days)
    ]


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def test_mae_matches_hand_calculation():
    assert mae([10, 20, 30], [12, 18, 33]) == pytest.approx((2 + 2 + 3) / 3)


def test_rmse_matches_hand_calculation():
    assert rmse([10, 20], [13, 24]) == pytest.approx(np.sqrt((9 + 16) / 2))


def test_wape_matches_hand_calculation():
    assert wape([10, 20, 30], [12, 18, 33]) == pytest.approx(7 / 60)


def test_perfect_prediction_scores_zero():
    scores = evaluate([5, 10, 15], [5, 10, 15])
    assert scores == {"mae": 0.0, "rmse": 0.0, "wape": 0.0}


def test_wape_is_nan_when_all_actuals_are_zero():
    """Zero total demand makes the percentage undefined, not perfect."""
    assert np.isnan(wape([0, 0, 0], [1, 2, 3]))


def test_rmse_is_at_least_mae():
    actual, predicted = [1, 5, 9, 20], [2, 9, 8, 11]
    assert rmse(actual, predicted) >= mae(actual, predicted)


def test_moving_average_baseline_uses_shifted_window():
    frame = build_features(make_history(), PRODUCT)
    assert np.allclose(moving_average_baseline(frame), frame["rolling_mean_7"])


def test_moving_average_baseline_requires_features():
    import pandas as pd

    with pytest.raises(KeyError):
        moving_average_baseline(pd.DataFrame({"quantity": [1, 2, 3]}))


def test_flat_baseline_divides_by_seven_days_not_row_count():
    """Sparse histories must not inflate the baseline by ignoring zero days."""
    history = [
        {"sale_date": date(2026, 1, 1), "quantity": 7},
        {"sale_date": date(2026, 1, 7), "quantity": 7},
    ]
    assert flat_baseline_forecast(history, 7) == pytest.approx(2.0)


def test_comparison_table_renders_every_model():
    table = comparison_table({"A": {"mae": 1.0, "rmse": 2.0, "wape": 0.25}})
    assert "A" in table and "25.00%" in table


# --------------------------------------------------------------------------
# Forecasting
# --------------------------------------------------------------------------


def test_forecast_returns_requested_number_of_days():
    for days in (7, 14, 30):
        assert len(forecast(make_history(), PRODUCT, days=days, model_bundle=bundle())) == days


def test_forecast_dates_are_consecutive_and_start_after_history():
    history = make_history()
    last = max(row["sale_date"] for row in history)

    rows = forecast(history, PRODUCT, days=7, model_bundle=bundle())
    dates = [date.fromisoformat(row["date"]) for row in rows]

    assert dates[0] == last + timedelta(days=1)
    assert dates == [dates[0] + timedelta(days=i) for i in range(7)]


def test_forecast_returns_whole_units():
    rows = forecast(make_history(), PRODUCT, days=7, model_bundle=bundle(12.7))
    assert all(isinstance(row["predicted_demand"], int) for row in rows)


def test_negative_predictions_are_clipped_to_zero():
    """Demand cannot be negative, whatever the regressor says."""
    rows = forecast(make_history(), PRODUCT, days=7, model_bundle=bundle(-50.0))
    assert all(row["predicted_demand"] == 0 for row in rows)


def test_forecast_units_sums_the_horizon():
    rows = forecast(make_history(), PRODUCT, days=7, model_bundle=bundle(10.0))
    total = forecast_units(make_history(), PRODUCT, days=7, model_bundle=bundle(10.0))
    assert total == sum(row["predicted_demand"] for row in rows)


def test_forecast_rejects_non_positive_horizon():
    with pytest.raises(ValueError):
        forecast(make_history(), PRODUCT, days=0, model_bundle=bundle())


def test_forecast_rejects_history_shorter_than_feature_window():
    with pytest.raises(InsufficientHistoryError):
        forecast(make_history(10), PRODUCT, days=7, model_bundle=bundle())


def test_forecast_rejects_empty_history():
    with pytest.raises(InsufficientHistoryError):
        forecast([], PRODUCT, days=7, model_bundle=bundle())


def test_sparse_history_is_measured_in_days_not_rows():
    """40 sales rows spread over 120 days is enough history; 40 days is not."""
    sparse = [
        {"sale_date": date(2026, 1, 1) + timedelta(days=i * 3), "quantity": 5, "avg_price": 33.0}
        for i in range(40)
    ]
    assert len(forecast(sparse, PRODUCT, days=7, model_bundle=bundle())) == 7


def test_forecast_is_deterministic():
    history = make_history()
    first = forecast(history, PRODUCT, days=14, model_bundle=bundle())
    second = forecast(history, PRODUCT, days=14, model_bundle=bundle())
    assert first == second


def test_forecast_does_not_mutate_the_caller_history():
    history = make_history()
    before = len(history)
    forecast(history, PRODUCT, days=7, model_bundle=bundle())
    assert len(history) == before
