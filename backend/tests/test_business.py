"""Customers, expenses, notifications, dashboard, analytics and reports."""

from __future__ import annotations

import csv
import io
from datetime import date

import pytest


def sell(client, headers, product, quantity=1, **extra):
    return client.post(
        "/pos/checkout",
        headers=headers,
        json={"items": [{"product_id": product["id"], "quantity": quantity}], **extra},
    ).json()


# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------


def test_customer_totals_come_from_their_invoices(client, headers, product):
    sale = sell(client, headers, product, 2, customer_name="Anita", customer_phone="9111111111")
    customer = client.get(f"/customers/{sale['customer_id']}", headers=headers).json()

    assert customer["purchase_count"] == 1
    assert float(customer["total_spent"]) == float(sale["total"])
    assert customer["average_order_value"] == float(sale["total"])
    assert customer["last_purchase"] == sale["sale_date"]


def test_customer_detail_lists_their_purchases(client, headers, product):
    sale = sell(client, headers, product, 1, customer_phone="9111111112")
    detail = client.get(f"/customers/{sale['customer_id']}", headers=headers).json()
    assert [row["invoice_number"] for row in detail["purchases"]] == [sale["invoice_number"]]


def test_duplicate_customer_phone_is_a_conflict(client, headers):
    client.post("/customers", headers=headers, json={"name": "A", "phone": "9222222222"})
    response = client.post("/customers", headers=headers, json={"name": "B", "phone": "9222222222"})
    assert response.status_code == 409


def test_customers_can_be_searched_by_phone(client, headers):
    client.post("/customers", headers=headers, json={"name": "Ravi", "phone": "9333333333"})
    found = client.get("/customers", headers=headers, params={"search": "9333"}).json()
    assert found["total"] == 1


def test_deleting_a_customer_keeps_their_invoices(client, headers, product):
    sale = sell(client, headers, product, 1, customer_name="Gone", customer_phone="9444444444")
    client.delete(f"/customers/{sale['customer_id']}", headers=headers)

    kept = client.get(f"/sales/{sale['id']}", headers=headers).json()
    assert kept["customer_name"] == "Gone"
    assert kept["customer_id"] is None


# --------------------------------------------------------------------------
# Expenses
# --------------------------------------------------------------------------


def test_expenses_are_totalled_and_grouped(client, headers):
    for category, amount in [("Rent", "10000"), ("Electricity", "2500"), ("Rent", "500")]:
        client.post(
            "/expenses",
            headers=headers,
            json={"category": category, "amount": amount, "expense_date": "2026-09-01"},
        )

    listed = client.get("/expenses", headers=headers).json()
    assert listed["total"] == 3
    assert listed["total_amount"] == 13000.0

    rent = next(row for row in listed["by_category"] if row["category"] == "Rent")
    assert rent["total"] == 10500.0
    assert rent["entries"] == 2


def test_expenses_can_be_filtered_by_date(client, headers):
    client.post(
        "/expenses",
        headers=headers,
        json={"category": "Rent", "amount": "100", "expense_date": "2026-01-01"},
    )
    client.post(
        "/expenses",
        headers=headers,
        json={"category": "Rent", "amount": "200", "expense_date": "2026-06-01"},
    )

    found = client.get(
        "/expenses", headers=headers, params={"start_date": "2026-05-01", "end_date": "2026-07-01"}
    ).json()
    assert found["total"] == 1
    assert found["total_amount"] == 200.0


def test_a_negative_expense_is_rejected(client, headers):
    response = client.post(
        "/expenses",
        headers=headers,
        json={"category": "Rent", "amount": "-100", "expense_date": "2026-01-01"},
    )
    assert response.status_code == 422


def test_an_unknown_expense_category_is_rejected(client, headers):
    response = client.post(
        "/expenses",
        headers=headers,
        json={"category": "Yachts", "amount": "100", "expense_date": "2026-01-01"},
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Profit
# --------------------------------------------------------------------------


def test_gross_profit_excludes_tax_and_subtracts_cost(client, headers, product):
    """50 sell, 30 cost, 5% tax: two units net 100 revenue, 60 cost, 40 profit."""
    sell(client, headers, product, 2)

    profit = client.get("/analytics/profit", headers=headers, params={"period": "7d"}).json()
    assert profit["net_revenue"] == 100.0
    assert profit["cost_of_goods"] == 60.0
    assert profit["gross_profit"] == 40.0
    assert profit["gross_margin_pct"] == 40.0


def test_operating_profit_subtracts_recorded_expenses(client, headers, product):
    sell(client, headers, product, 2)
    client.post(
        "/expenses",
        headers=headers,
        json={
            "category": "Rent",
            "amount": "15.00",
            "expense_date": date.today().isoformat(),
        },
    )

    profit = client.get("/analytics/profit", headers=headers, params={"period": "7d"}).json()
    assert profit["recorded_expenses"] == 15.0
    assert profit["estimated_operating_profit"] == 25.0


def test_operating_profit_is_labelled_as_an_estimate(client, headers):
    """Calling this 'profit' would be a claim the data does not support."""
    profit = client.get("/analytics/profit", headers=headers).json()
    assert "estimate" in profit["note"].lower()
    assert "not a full accounting profit" in profit["note"]


def test_margin_on_no_revenue_is_undefined_not_zero(client, headers):
    profit = client.get("/analytics/profit", headers=headers, params={"period": "today"}).json()
    assert profit["revenue"] == 0
    assert profit["gross_margin_pct"] is None


# --------------------------------------------------------------------------
# Dashboard and briefing
# --------------------------------------------------------------------------


def test_dashboard_reports_todays_trade(client, headers, product):
    sale = sell(client, headers, product, 3)
    dashboard = client.get("/dashboard", headers=headers).json()

    assert dashboard["today"]["orders"] == 1
    assert dashboard["today"]["revenue"] == float(sale["total"])
    assert dashboard["today"]["units"] == 3


def test_dashboard_works_without_a_forecast(client, headers, product):
    """A store with no history still sees its revenue and stock."""
    dashboard = client.get("/dashboard", headers=headers).json()
    assert dashboard["inventory"]["total_products"] == 1
    assert dashboard["reorders"] == []


def test_dashboard_revenue_series_includes_days_with_no_sales(client, headers):
    """A closed day is a flat line, not a gap."""
    series = client.get("/dashboard", headers=headers).json()["revenue_series"]
    assert len(series) == 7
    assert all(float(point["revenue"]) == 0 for point in series)


def test_briefing_greets_the_signed_in_user(client, headers, store):
    briefing = client.get("/briefing", headers=headers).json()
    assert briefing["user_name"] == store["owner"]["user"]["full_name"]
    assert briefing["greeting"].startswith("Good ")


def test_briefing_flags_out_of_stock_products(client, headers, product_factory):
    product_factory(current_stock=0, reorder_level=5)
    briefing = client.get("/briefing", headers=headers).json()
    assert any("out of stock" in line["text"] for line in briefing["headlines"])


def test_briefing_actions_explain_themselves(client, demo_headers):
    briefing = client.get("/briefing", headers=demo_headers).json()
    for action in briefing["actions"]:
        assert action["detail"]
        assert action["link"]


# --------------------------------------------------------------------------
# Analytics
# --------------------------------------------------------------------------


def test_sales_analytics_splits_by_payment_method(client, headers, product):
    sell(client, headers, product, 1, payment_method="UPI")
    sell(client, headers, product, 1, payment_method="CASH")
    sell(client, headers, product, 1, payment_method="CASH")

    analytics = client.get("/analytics/sales", headers=headers, params={"period": "7d"}).json()
    split = {row["payment_method"]: row["orders"] for row in analytics["payment_split"]}
    assert split == {"CASH": 2, "UPI": 1}
    assert analytics["orders"] == 3


def test_average_order_value_is_reported(client, headers, product):
    sell(client, headers, product, 2)
    analytics = client.get("/analytics/sales", headers=headers, params={"period": "7d"}).json()
    assert analytics["average_order_value"] == 105.0


def test_product_analytics_separates_non_sellers_from_slow_sellers(
    client, headers, product_factory
):
    sold = product_factory()
    product_factory()
    sell(client, headers, sold, 5)

    analytics = client.get(
        "/analytics/products", headers=headers, params={"period": "7d"}
    ).json()
    assert [row["product_id"] for row in analytics["best_sellers"]] == [sold["id"]]
    assert len(analytics["no_sales"]) == 1


def test_inventory_analytics_finds_dead_stock(client, headers, product_factory):
    dead = product_factory(current_stock=40, cost_price="10.00")
    analytics = client.get(
        "/analytics/inventory", headers=headers, params={"period": "30d"}
    ).json()

    assert any(row["product_id"] == dead["id"] for row in analytics["dead_stock"])
    assert analytics["dead_stock_value"] == 400.0


def test_stock_turnover_is_undefined_with_no_inventory(client, headers):
    analytics = client.get("/analytics/inventory", headers=headers).json()
    assert analytics["stock_turnover"] is None


def test_category_contribution_sums_to_a_hundred(client, headers, product_factory):
    sell(client, headers, product_factory(category="Dairy"), 2)
    sell(client, headers, product_factory(category="Snacks"), 1)

    categories = client.get("/analytics/categories", headers=headers, params={"days": 30}).json()
    contributions = [row["contribution_pct"] for row in categories if row["contribution_pct"]]
    assert sum(contributions) == pytest.approx(100.0, abs=0.5)


def test_an_inverted_date_range_is_rejected(client, headers):
    response = client.get(
        "/analytics/sales",
        headers=headers,
        params={"start_date": "2026-09-01", "end_date": "2026-01-01"},
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------


def test_out_of_stock_products_raise_a_notification(client, headers, product_factory):
    product_factory(current_stock=0, name="Vanished Item")
    client.post("/notifications/refresh", headers=headers)

    listed = client.get("/notifications", headers=headers).json()
    assert any("Vanished Item" in row["title"] for row in listed["items"])
    assert listed["unread"] > 0


def test_refreshing_twice_does_not_duplicate_alerts(client, headers, product_factory):
    """Regenerated alerts must update in place, not pile up."""
    product_factory(current_stock=0)
    client.post("/notifications/refresh", headers=headers)
    first = client.get("/notifications", headers=headers).json()["items"]

    client.post("/notifications/refresh", headers=headers)
    second = client.get("/notifications", headers=headers).json()["items"]

    assert len(first) == len(second)


def test_notifications_can_be_marked_read(client, headers, product_factory):
    product_factory(current_stock=0)
    client.post("/notifications/refresh", headers=headers)
    notification = client.get("/notifications", headers=headers).json()["items"][0]

    updated = client.patch(
        f"/notifications/{notification['id']}/read", headers=headers, json={"is_read": True}
    ).json()
    assert updated["is_read"] is True
    assert client.get("/notifications", headers=headers).json()["unread"] == 0


def test_mark_all_read_clears_the_badge(client, headers, product_factory):
    product_factory(current_stock=0)
    product_factory(current_stock=0)
    client.post("/notifications/refresh", headers=headers)

    client.post("/notifications/read-all", headers=headers)
    assert client.get("/notifications", headers=headers).json()["unread"] == 0


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


def test_search_spans_products_invoices_and_customers(client, headers, product_factory):
    product = product_factory(name="Findable Milk", sku="FIND-1")
    sale = sell(client, headers, product, 1, customer_name="Findable Person",
                customer_phone="9555555555")

    products = client.get("/search", headers=headers, params={"q": "Findable"}).json()
    assert any(row["label"] == "Findable Milk" for row in products["products"])
    assert any(row["label"] == "Findable Person" for row in products["customers"])

    invoices = client.get(
        "/search", headers=headers, params={"q": sale["invoice_number"]}
    ).json()
    assert invoices["sales"][0]["label"] == sale["invoice_number"]


def test_search_results_carry_a_link(client, headers, product):
    results = client.get("/search", headers=headers, params={"q": product["sku"]}).json()
    assert results["products"][0]["link"] == f"/products/{product['id']}"


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


def test_reports_are_listed_with_descriptions(client, headers):
    reports = client.get("/reports", headers=headers).json()
    assert len(reports) >= 8
    assert all(row["label"] and row["description"] for row in reports)


@pytest.mark.parametrize(
    "report",
    ["daily-sales", "invoices", "product-sales", "inventory", "low-stock",
     "profit", "tax", "purchases", "expenses"],
)
def test_every_report_downloads_as_csv(client, headers, product, report):
    sell(client, headers, product, 2)

    response = client.get(f"/reports/{report}", headers=headers, params={"period": "30d"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows and rows[0], f"{report} produced no header row"


def test_report_figures_match_the_api(client, headers, product):
    sell(client, headers, product, 2)

    csv_text = client.get(
        "/reports/profit", headers=headers, params={"period": "30d"}
    ).text
    rows = {row["metric"]: float(row["amount"]) for row in csv.DictReader(io.StringIO(csv_text))}
    api = client.get("/analytics/profit", headers=headers, params={"period": "30d"}).json()

    assert rows["Gross profit"] == api["gross_profit"]
    assert rows["Cost of goods sold"] == api["cost_of_goods"]


def test_an_unknown_report_is_rejected(client, headers):
    assert client.get("/reports/made-up", headers=headers).status_code == 422
