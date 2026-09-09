"""Feature engineering tests.

The leakage tests are the important ones. If a feature for day D can see day D's
demand — or any later day's — then every metric the project reports is a lie,
and the failure is invisible without a test like these.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.ml.feature_engineering import (
    CATEGORIES,
    FEATURE_COLUMNS,
    add_event_features,
    build_daily_frame,
    build_features,
    chronological_split,
    load_events,
)

PRODUCT = {
    "id": 1,
    "sku": "TEST-001",
    "name": "Test Milk 1L",
    "category": "Dairy",
    "unit_price": 33.0,
}


def make_history(days: int = 120, start: date = date(2026, 1, 1)) -> list[dict]:
    """A deterministic ramp; distinct values make lag alignment checkable."""
    return [
        {"sale_date": start + timedelta(days=i), "quantity": 10 + i, "avg_price": 33.0}
        for i in range(days)
    ]


@pytest.fixture(scope="module")
def events():
    return load_events()


# --------------------------------------------------------------------------
# Leakage
# --------------------------------------------------------------------------


def test_features_do_not_use_same_day_demand(events):
    """Changing day D's quantity must not change day D's features."""
    history = make_history()
    baseline = build_features(history, PRODUCT, events=events)

    target = baseline.iloc[-1]["sale_date"]

    tampered = [dict(row) for row in history]
    tampered[-1]["quantity"] = 99_999
    after = build_features(tampered, PRODUCT, events=events)

    before_row = baseline[baseline["sale_date"] == target][FEATURE_COLUMNS].iloc[0]
    after_row = after[after["sale_date"] == target][FEATURE_COLUMNS].iloc[0]

    pd.testing.assert_series_equal(before_row, after_row, check_names=False)


def test_features_do_not_use_future_demand(events):
    """Appending later days must not change features for an earlier day."""
    history = make_history(90)
    short = build_features(history, PRODUCT, events=events)
    target = short.iloc[-1]["sale_date"]

    extended = history + [
        {"sale_date": date(2026, 4, 1) + timedelta(days=i), "quantity": 5000, "avg_price": 33.0}
        for i in range(10)
    ]
    long = build_features(extended, PRODUCT, events=events)

    short_row = short[short["sale_date"] == target][FEATURE_COLUMNS].iloc[0]
    long_row = long[long["sale_date"] == target][FEATURE_COLUMNS].iloc[0]

    pd.testing.assert_series_equal(short_row, long_row, check_names=False)


def test_lag_1_equals_previous_day_quantity(events):
    frame = build_features(make_history(), PRODUCT, events=events)
    assert (frame["lag_1"].to_numpy()[1:] == frame["quantity"].to_numpy()[:-1]).all()


def test_lag_7_equals_quantity_seven_days_earlier(events):
    frame = build_features(make_history(), PRODUCT, events=events)
    assert (frame["lag_7"].to_numpy()[7:] == frame["quantity"].to_numpy()[:-7]).all()


def test_rolling_mean_7_excludes_current_day(events):
    frame = build_features(make_history(), PRODUCT, events=events)
    row = frame.iloc[40]
    position = frame.index.get_loc(40)
    previous_seven = frame["quantity"].to_numpy()[position - 7 : position]
    assert row["rolling_mean_7"] == pytest.approx(previous_seven.mean())


def test_rolling_std_7_excludes_current_day(events):
    frame = build_features(make_history(), PRODUCT, events=events)
    row = frame.iloc[40]
    previous_seven = frame["quantity"].to_numpy()[33:40]
    assert row["rolling_std_7"] == pytest.approx(previous_seven.std(ddof=1))


# --------------------------------------------------------------------------
# Daily frame construction
# --------------------------------------------------------------------------


def test_missing_days_become_zero_not_gaps():
    """A day absent from the sales table is a real zero-sale day."""
    history = [
        {"sale_date": date(2026, 1, 1), "quantity": 10},
        {"sale_date": date(2026, 1, 5), "quantity": 20},
    ]
    frame = build_daily_frame(history)

    assert len(frame) == 5
    assert frame["quantity"].tolist() == [10.0, 0.0, 0.0, 0.0, 20.0]


def test_daily_frame_aggregates_multiple_rows_per_day():
    history = [
        {"sale_date": date(2026, 1, 1), "quantity": 4},
        {"sale_date": date(2026, 1, 1), "quantity": 6},
    ]
    assert build_daily_frame(history)["quantity"].tolist() == [10.0]


def test_empty_history_yields_empty_frame():
    assert build_daily_frame([]).empty


def test_build_features_on_empty_history_returns_empty_frame(events):
    assert build_features([], PRODUCT, events=events).empty


# --------------------------------------------------------------------------
# Calendar, product and event features
# --------------------------------------------------------------------------


def test_weekend_flag_matches_calendar(events):
    frame = build_features(make_history(), PRODUCT, events=events)
    expected = (frame["sale_date"].dt.dayofweek >= 5).astype(int)
    assert (frame["is_weekend"] == expected).all()


def test_category_is_one_hot_encoded(events):
    frame = build_features(make_history(), PRODUCT, events=events)
    assert frame["category_Dairy"].eq(1).all()
    for other in CATEGORIES:
        if other != "Dairy":
            assert frame[f"category_{other}"].eq(0).all()


def test_promotion_flag_set_when_price_drops_below_list():
    history = make_history(90)
    history[-1]["avg_price"] = 25.0  # list price is 33.0
    frame = build_features(history, PRODUCT, dropna=False)
    assert frame.iloc[-1]["promotion_flag"] == 1
    assert frame.iloc[-2]["promotion_flag"] == 0


def test_festival_impact_upcoming_looks_three_days_ahead():
    """Event dates are known in advance, so looking ahead is intentional."""
    events = pd.DataFrame(
        [{"date": date(2026, 1, 20), "event_name": "Test", "affected_category": "Dairy",
          "impact_score": 0.5}]
    )
    frame = build_daily_frame(make_history(40))
    frame = add_event_features(frame, events, "Dairy")
    indexed = frame.set_index(frame["sale_date"].dt.date)

    assert indexed.loc[date(2026, 1, 17), "festival_impact_upcoming"] == 0.5
    assert indexed.loc[date(2026, 1, 20), "festival_impact"] == 0.5
    assert indexed.loc[date(2026, 1, 15), "festival_impact_upcoming"] == 0.0


def test_event_for_other_category_is_ignored():
    events = pd.DataFrame(
        [{"date": date(2026, 1, 20), "event_name": "Test", "affected_category": "Snacks",
          "impact_score": 0.5}]
    )
    frame = add_event_features(build_daily_frame(make_history(40)), events, "Dairy")
    assert frame["festival_impact"].sum() == 0.0


def test_all_category_event_applies_to_every_product():
    events = pd.DataFrame(
        [{"date": date(2026, 1, 20), "event_name": "Test", "affected_category": "ALL",
          "impact_score": 0.4}]
    )
    frame = add_event_features(build_daily_frame(make_history(40)), events, "Dairy")
    assert frame["festival_impact"].max() == pytest.approx(0.4)


def test_all_declared_features_are_present_and_finite(events):
    frame = build_features(make_history(), PRODUCT, events=events)
    assert set(FEATURE_COLUMNS) <= set(frame.columns)
    assert np.isfinite(frame[FEATURE_COLUMNS].to_numpy()).all()


def test_growth_features_survive_zero_demand_windows(events):
    """A product that sold nothing must not produce inf or NaN growth."""
    history = [
        {"sale_date": date(2026, 1, 1) + timedelta(days=i), "quantity": 0, "avg_price": 33.0}
        for i in range(70)
    ]
    history += [
        {"sale_date": date(2026, 3, 12) + timedelta(days=i), "quantity": 15, "avg_price": 33.0}
        for i in range(30)
    ]
    frame = build_features(history, PRODUCT, events=events)
    growth = frame[["recent_7_day_growth", "recent_30_day_growth"]].to_numpy()
    assert np.isfinite(growth).all()


# --------------------------------------------------------------------------
# Splitting
# --------------------------------------------------------------------------


def test_split_is_chronological_and_non_overlapping(events):
    frame = build_features(make_history(200), PRODUCT, events=events)
    train, validation, test = chronological_split(frame)

    assert train["sale_date"].max() < validation["sale_date"].min()
    assert validation["sale_date"].max() < test["sale_date"].min()


def test_split_preserves_every_row(events):
    frame = build_features(make_history(200), PRODUCT, events=events)
    train, validation, test = chronological_split(frame)
    assert len(train) + len(validation) + len(test) == len(frame)


def test_split_proportions_are_roughly_as_requested(events):
    frame = build_features(make_history(300), PRODUCT, events=events)
    train, validation, test = chronological_split(frame)
    assert 0.65 <= len(train) / len(frame) <= 0.75
    assert 0.10 <= len(validation) / len(frame) <= 0.20


def test_split_rejects_too_few_dates():
    frame = pd.DataFrame({"sale_date": pd.to_datetime(["2026-01-01", "2026-01-02"])})
    with pytest.raises(ValueError):
        chronological_split(frame)
