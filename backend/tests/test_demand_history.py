"""Demand history: the bridge between the POS and the forecasting model.

The old `POST /sales` endpoint is gone — sales are created at the till, and the
aggregation the model trains on is derived from those line items. These tests
cover that derivation; the checkout itself is covered by test_pos.py.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models import sale as sale_model


def sell(client, headers, product, quantity, on_date=None):
    payload = {"items": [{"product_id": product["id"], "quantity": quantity}]}
    if on_date:
        payload["sale_date"] = on_date.isoformat()
    response = client.post("/pos/checkout", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_checkout_becomes_demand_history(client, headers, product, store):
    sell(client, headers, product, 5)

    history = sale_model.daily_history(product["id"], store["id"])
    assert len(history) == 1
    assert history[0]["quantity"] == 5


def test_same_day_sales_are_aggregated(client, headers, product, store):
    """The model sees demand per day, not per invoice."""
    today = date.today()
    sell(client, headers, product, 3, today)
    sell(client, headers, product, 4, today)

    history = sale_model.daily_history(product["id"], store["id"])
    assert len(history) == 1
    assert history[0]["quantity"] == 7


def test_history_is_chronological(client, headers, product, store):
    today = date.today()
    sell(client, headers, product, 2, today - timedelta(days=2))
    sell(client, headers, product, 3, today)
    sell(client, headers, product, 1, today - timedelta(days=1))

    history = sale_model.daily_history(product["id"], store["id"])
    dates = [row["sale_date"] for row in history]
    assert dates == sorted(dates)


def test_history_records_the_average_price(client, headers, product, store):
    """The average price drives the promotion flag in the feature pipeline."""
    sell(client, headers, product, 1)
    history = sale_model.daily_history(product["id"], store["id"])
    assert float(history[0]["avg_price"]) == 50.0


def test_days_without_sales_are_absent_not_zero(client, headers, product, store):
    """The feature pipeline reindexes onto a full calendar and fills the gaps."""
    today = date.today()
    sell(client, headers, product, 2, today - timedelta(days=5))
    sell(client, headers, product, 2, today)

    history = sale_model.daily_history(product["id"], store["id"])
    assert len(history) == 2


def test_cancelled_invoices_are_excluded(client, headers, product, store):
    sale = sell(client, headers, product, 9)
    client.post(f"/sales/{sale['id']}/cancel", headers=headers, json={})
    assert sale_model.daily_history(product["id"], store["id"]) == []


def test_history_is_scoped_to_one_store(client, headers, product, store, new_user):
    sell(client, headers, product, 4)

    outsider = new_user()
    other = client.post("/stores", headers=outsider["headers"], json={"name": "Other"}).json()
    assert sale_model.daily_history(product["id"], other["id"]) == []


def test_summary_reports_the_span_of_history(client, headers, product, store):
    today = date.today()
    sell(client, headers, product, 2, today - timedelta(days=10))
    sell(client, headers, product, 3, today)

    summary = sale_model.sales_summary(product["id"], store["id"])
    assert summary["total_units"] == 5
    assert summary["first_sale_date"] == today - timedelta(days=10)
    assert summary["last_sale_date"] == today


def test_a_product_never_sold_has_no_history(client, headers, product, store):
    assert sale_model.daily_history(product["id"], store["id"]) == []


def test_the_seeded_store_has_a_year_of_history(demo_store_id):
    if demo_store_id is None:
        pytest.skip("no demo store; run scripts/seed_demo.py")

    from app.models import product as product_model

    products = product_model.list_products(demo_store_id, limit=1)
    history = sale_model.daily_history(products[0]["id"], demo_store_id)
    span = (history[-1]["sale_date"] - history[0]["sale_date"]).days
    assert span > 300
