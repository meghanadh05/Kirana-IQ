"""Tests for the synthetic data generator.

These guard the properties the forecasting model depends on: reproducibility,
complete coverage, and the presence of real weekly/festival structure.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_data as gen  # noqa: E402


@pytest.fixture(scope="module")
def events():
    return gen.load_events(gen.EVENTS_PATH)


def test_catalogue_has_30_products_across_7_categories():
    categories = {row[3] for row in gen.PRODUCT_CATALOGUE}
    assert len(gen.PRODUCT_CATALOGUE) == 30
    assert len(categories) == 7
    assert categories == set(gen.CATEGORY_PROFILE)


def test_skus_are_unique():
    products = gen.build_products(np.random.default_rng(1))
    skus = [p["sku"] for p in products]
    assert len(skus) == len(set(skus))


def test_generation_is_reproducible(events):
    def run():
        rng = np.random.default_rng(7)
        products = gen.build_products(rng)
        return gen.generate_sales(products, date(2026, 1, 1), date(2026, 1, 31), events, rng)

    assert run() == run()


def test_different_seeds_produce_different_data(events):
    def run(seed):
        rng = np.random.default_rng(seed)
        products = gen.build_products(rng)
        return gen.generate_sales(products, date(2026, 1, 1), date(2026, 1, 31), events, rng)

    assert run(1) != run(2)


def test_quantities_are_positive_integers(events):
    rng = np.random.default_rng(3)
    products = gen.build_products(rng)
    rows = gen.generate_sales(products, date(2026, 1, 1), date(2026, 1, 31), events, rng)
    assert rows
    assert all(isinstance(r["quantity"], int) and r["quantity"] > 0 for r in rows)


def test_weekend_demand_exceeds_weekday_demand(events):
    rng = np.random.default_rng(11)
    products = gen.build_products(rng)
    rows = gen.generate_sales(products, date(2025, 9, 9), date(2026, 9, 8), events, rng)

    weekend = weekday = 0
    weekend_days: set[date] = set()
    weekday_days: set[date] = set()
    for row in rows:
        day = date.fromisoformat(row["sale_date"])
        if day.weekday() >= 5:
            weekend += row["quantity"]
            weekend_days.add(day)
        else:
            weekday += row["quantity"]
            weekday_days.add(day)

    assert weekend / len(weekend_days) > weekday / len(weekday_days)


def test_festival_lifts_demand_for_affected_category(events):
    """Diwali should lift Snacks demand above the surrounding baseline."""
    rng = np.random.default_rng(13)
    products = [p for p in gen.build_products(rng) if p["category"] == "Snacks"]
    rows = gen.generate_sales(products, date(2025, 10, 1), date(2025, 10, 31), events, rng)

    daily: dict[date, int] = {}
    for row in rows:
        day = date.fromisoformat(row["sale_date"])
        daily[day] = daily.get(day, 0) + row["quantity"]

    spike = [daily.get(date(2025, 10, d), 0) for d in range(17, 21)]
    baseline = [daily.get(date(2025, 10, d), 0) for d in range(1, 11)]

    assert sum(spike) / len(spike) > sum(baseline) / len(baseline)


def test_event_factor_is_one_away_from_events(events):
    assert gen.event_factor(date(2026, 6, 15), "Snacks", events) == 1.0


def test_event_factor_ignores_unaffected_category(events):
    diwali = [e for e in events if e["event_name"] == "Diwali" and e["affected_category"] == "Snacks"]
    assert diwali, "expected a Diwali/Snacks row in events.csv"
    # Personal Care is not in any Diwali row, and Diwali's ALL row still applies.
    snacks = gen.event_factor(date(2025, 10, 20), "Snacks", events)
    personal_care = gen.event_factor(date(2025, 10, 20), "Personal Care", events)
    assert snacks > personal_care


def test_events_csv_is_well_formed(events):
    assert len(events) > 0
    known = set(gen.CATEGORY_PROFILE) | {"ALL"}
    for event in events:
        assert event["affected_category"] in known, event
        assert 0 < event["impact_score"] <= 1.0, event


def test_stock_assignment_produces_a_mix_of_cover_levels(events):
    rng = np.random.default_rng(42)
    products = gen.build_products(rng)
    end = date(2026, 9, 8)
    rows = gen.generate_sales(products, date(2025, 9, 9), end, events, rng)
    gen.assign_stock(products, rows, end, rng)

    assert all(p["current_stock"] >= 0 for p in products)
    assert all(p["reorder_level"] >= 1 for p in products)

    covers = [
        p["current_stock"] / p["avg_daily_recent"]
        for p in products
        if p["avg_daily_recent"] > 0
    ]
    assert any(c <= 3 for c in covers), "expected some near-stockout products"
    assert any(c > 30 for c in covers), "expected some overstocked products"
