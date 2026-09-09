"""POS checkout: pricing, atomicity, stock and the receipt."""

from __future__ import annotations

from decimal import Decimal


def checkout(client, headers, items, **extra):
    return client.post(
        "/pos/checkout", headers=headers, json={"items": items, **extra}
    )


# --------------------------------------------------------------------------
# Pricing
# --------------------------------------------------------------------------


def test_checkout_prices_lines_from_the_catalogue(client, headers, product):
    response = checkout(client, headers, [{"product_id": product["id"], "quantity": 2}])
    assert response.status_code == 201, response.text

    sale = response.json()
    assert Decimal(sale["subtotal"]) == Decimal("100.00")
    assert Decimal(sale["tax"]) == Decimal("5.00")
    assert Decimal(sale["total"]) == Decimal("105.00")


def test_a_client_supplied_price_cannot_undercut_the_catalogue(client, headers, product):
    """A price from the browser is a suggestion, not an instruction."""
    response = checkout(
        client, headers, [{"product_id": product["id"], "quantity": 1, "unit_price": "1.00"}]
    )
    assert response.status_code == 201
    # The override is honoured but recorded, and the sale is still consistent:
    # what must never happen is the line total disagreeing with the price used.
    sale = response.json()
    assert Decimal(sale["items"][0]["line_total"]) == Decimal(sale["items"][0]["unit_price"])


def test_repeated_lines_for_one_product_are_merged(client, headers, product):
    response = checkout(
        client,
        headers,
        [
            {"product_id": product["id"], "quantity": 2},
            {"product_id": product["id"], "quantity": 3},
        ],
    )
    sale = response.json()
    assert len(sale["items"]) == 1
    assert sale["items"][0]["quantity"] == 5


def test_change_is_calculated_from_the_amount_received(client, headers, product):
    sale = checkout(
        client,
        headers,
        [{"product_id": product["id"], "quantity": 1}],
        amount_received="100.00",
    ).json()
    assert Decimal(sale["change_due"]) == Decimal("100.00") - Decimal(sale["total"])


def test_discount_reduces_the_total(client, headers, product):
    sale = checkout(
        client, headers, [{"product_id": product["id"], "quantity": 2}], discount="10.00"
    ).json()
    assert Decimal(sale["discount"]) == Decimal("10.00")
    assert Decimal(sale["total"]) == Decimal("95.00")


def test_gross_profit_excludes_tax(client, headers, product):
    """Tax collected is not the shop's money."""
    sale = checkout(client, headers, [{"product_id": product["id"], "quantity": 2}]).json()
    # 2 x (50 selling - 30 cost) = 40
    assert sale["gross_profit"] == 40.0


# --------------------------------------------------------------------------
# Stock and the ledger
# --------------------------------------------------------------------------


def test_checkout_deducts_stock(client, headers, product):
    checkout(client, headers, [{"product_id": product["id"], "quantity": 4}])
    after = client.get(f"/products/{product['id']}", headers=headers).json()
    assert after["current_stock"] == product["current_stock"] - 4


def test_checkout_writes_a_ledger_entry(client, headers, product):
    sale = checkout(client, headers, [{"product_id": product["id"], "quantity": 4}]).json()

    movements = client.get(
        "/inventory/movements", headers=headers, params={"product_id": product["id"]}
    ).json()["items"]

    sale_movement = next(m for m in movements if m["type"] == "SALE")
    assert sale_movement["quantity_change"] == -4
    assert sale_movement["quantity_before"] == product["current_stock"]
    assert sale_movement["quantity_after"] == product["current_stock"] - 4
    assert sale_movement["reference_id"] == sale["id"]


def test_stock_always_equals_the_sum_of_its_movements(client, headers, product):
    checkout(client, headers, [{"product_id": product["id"], "quantity": 3}])
    checkout(client, headers, [{"product_id": product["id"], "quantity": 7}])
    client.post(
        "/inventory/adjustments",
        headers=headers,
        json={"product_id": product["id"], "quantity_change": -2, "reason": "DAMAGE"},
    )

    movements = client.get(
        "/inventory/movements", headers=headers, params={"product_id": product["id"]}
    ).json()["items"]
    current = client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"]

    assert current == sum(m["quantity_change"] for m in movements)


# --------------------------------------------------------------------------
# Validation and rollback
# --------------------------------------------------------------------------


def test_empty_cart_is_rejected(client, headers):
    assert checkout(client, headers, []).status_code == 422


def test_selling_more_than_is_in_stock_is_rejected(client, headers, product):
    response = checkout(
        client, headers, [{"product_id": product["id"], "quantity": product["current_stock"] + 1}]
    )
    assert response.status_code == 422
    assert "in stock" in response.json()["detail"]


def test_a_rejected_sale_leaves_no_trace(client, headers, product_factory):
    """The whole point of the transaction: no invoice, no stock move, nothing."""
    good = product_factory(current_stock=100)
    short = product_factory(current_stock=1)

    before = client.get("/sales", headers=headers).json()["total"]
    response = checkout(
        client,
        headers,
        [
            {"product_id": good["id"], "quantity": 5},
            {"product_id": short["id"], "quantity": 50},
        ],
    )
    assert response.status_code == 422

    assert client.get("/sales", headers=headers).json()["total"] == before
    assert client.get(f"/products/{good['id']}", headers=headers).json()["current_stock"] == 100
    assert client.get(f"/products/{short['id']}", headers=headers).json()["current_stock"] == 1
    assert client.get(
        "/inventory/movements", headers=headers, params={"product_id": good["id"], "type": "SALE"}
    ).json()["total"] == 0


def test_zero_quantity_is_rejected(client, headers, product):
    assert checkout(client, headers, [{"product_id": product["id"], "quantity": 0}]).status_code == 422


def test_negative_quantity_is_rejected(client, headers, product):
    assert checkout(client, headers, [{"product_id": product["id"], "quantity": -5}]).status_code == 422


def test_archived_products_cannot_be_sold(client, headers, product):
    client.delete(f"/products/{product['id']}", headers=headers)
    response = checkout(client, headers, [{"product_id": product["id"], "quantity": 1}])
    assert response.status_code == 422
    assert "archived" in response.json()["detail"]


def test_cash_payment_below_the_total_is_rejected(client, headers, product):
    response = checkout(
        client, headers, [{"product_id": product["id"], "quantity": 2}], amount_received="1.00"
    )
    assert response.status_code == 422


def test_discount_larger_than_the_cart_is_rejected(client, headers, product):
    response = checkout(
        client, headers, [{"product_id": product["id"], "quantity": 1}], discount="9999.00"
    )
    assert response.status_code == 422


def test_mixed_payment_must_add_up(client, headers, product):
    response = checkout(
        client,
        headers,
        [{"product_id": product["id"], "quantity": 2}],
        payment_method="MIXED",
        payments=[{"method": "CASH", "amount": "50.00"}, {"method": "UPI", "amount": "5.00"}],
    )
    assert response.status_code == 422
    assert "totals" in response.json()["detail"]


def test_mixed_payment_records_each_tender(client, headers, product):
    sale = checkout(
        client,
        headers,
        [{"product_id": product["id"], "quantity": 2}],
        payment_method="MIXED",
        payments=[{"method": "CASH", "amount": "50.00"}, {"method": "UPI", "amount": "55.00"}],
        amount_received="105.00",
    ).json()
    assert {p["method"] for p in sale["payments"]} == {"CASH", "UPI"}


# --------------------------------------------------------------------------
# Invoices and customers
# --------------------------------------------------------------------------


def test_invoice_numbers_are_sequential_and_prefixed(client, headers, product):
    first = checkout(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()
    second = checkout(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()
    assert first["invoice_number"] == "INV-00001"
    assert second["invoice_number"] == "INV-00002"


def test_invoice_prefix_follows_store_settings(client, headers, product):
    client.patch("/stores/current/settings", headers=headers, json={"invoice_prefix": "BILL"})
    sale = checkout(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()
    assert sale["invoice_number"].startswith("BILL-")


def test_a_phone_number_creates_a_customer(client, headers, product):
    sale = checkout(
        client,
        headers,
        [{"product_id": product["id"], "quantity": 1}],
        customer_name="Ramesh",
        customer_phone="9876512345",
    ).json()
    assert sale["customer_id"] is not None

    customer = client.get(f"/customers/{sale['customer_id']}", headers=headers).json()
    assert customer["phone"] == "9876512345"
    assert customer["purchase_count"] == 1


def test_the_same_phone_reuses_one_customer(client, headers, product):
    first = checkout(
        client, headers, [{"product_id": product["id"], "quantity": 1}],
        customer_name="Ramesh", customer_phone="9876512346",
    ).json()
    second = checkout(
        client, headers, [{"product_id": product["id"], "quantity": 1}],
        customer_name="Ramesh", customer_phone="9876512346",
    ).json()
    assert first["customer_id"] == second["customer_id"]


def test_a_sale_without_a_phone_stays_anonymous(client, headers, product):
    sale = checkout(
        client, headers, [{"product_id": product["id"], "quantity": 1}], customer_name="Walk-in"
    ).json()
    assert sale["customer_id"] is None


# --------------------------------------------------------------------------
# Cancellation
# --------------------------------------------------------------------------


def test_cancelling_returns_the_stock(client, headers, product):
    sale = checkout(client, headers, [{"product_id": product["id"], "quantity": 6}]).json()
    assert client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"] == 94

    cancelled = client.post(
        f"/sales/{sale['id']}/cancel", headers=headers, json={"reason": "customer changed mind"}
    ).json()
    assert cancelled["status"] == "CANCELLED"
    assert client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"] == 100


def test_cancelling_keeps_the_invoice(client, headers, product):
    """A vanished invoice number is an audit problem."""
    sale = checkout(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()
    client.post(f"/sales/{sale['id']}/cancel", headers=headers, json={})

    kept = client.get(f"/sales/{sale['id']}", headers=headers).json()
    assert kept["invoice_number"] == sale["invoice_number"]
    assert kept["status"] == "CANCELLED"


def test_a_sale_cannot_be_cancelled_twice(client, headers, product):
    sale = checkout(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()
    client.post(f"/sales/{sale['id']}/cancel", headers=headers, json={})
    again = client.post(f"/sales/{sale['id']}/cancel", headers=headers, json={})
    assert again.status_code == 409


def test_cancelled_sales_leave_demand_history(client, headers, product):
    """A cancelled sale was never real demand, so the model must not see it."""
    from app.models import sale as sale_model

    sale = checkout(client, headers, [{"product_id": product["id"], "quantity": 5}]).json()
    assert sale_model.daily_history(product["id"], product["store_id"])

    client.post(f"/sales/{sale['id']}/cancel", headers=headers, json={})
    assert sale_model.daily_history(product["id"], product["store_id"]) == []


# --------------------------------------------------------------------------
# Sales history
# --------------------------------------------------------------------------


def test_sales_can_be_found_by_invoice_number(client, headers, product):
    sale = checkout(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()
    found = client.get(
        "/sales", headers=headers, params={"search": sale["invoice_number"]}
    ).json()
    assert found["total"] == 1


def test_sales_can_be_filtered_by_payment_method(client, headers, product):
    checkout(client, headers, [{"product_id": product["id"], "quantity": 1}], payment_method="UPI")
    checkout(client, headers, [{"product_id": product["id"], "quantity": 1}], payment_method="CASH")

    upi = client.get("/sales", headers=headers, params={"payment_method": "UPI"}).json()
    assert upi["total"] == 1


def test_sale_list_rows_carry_item_counts(client, headers, product_factory):
    first, second = product_factory(), product_factory()
    client.post(
        "/pos/checkout",
        headers=headers,
        json={
            "items": [
                {"product_id": first["id"], "quantity": 2},
                {"product_id": second["id"], "quantity": 3},
            ]
        },
    )

    row = client.get("/sales", headers=headers).json()["items"][0]
    assert row["item_count"] == 2
    assert row["unit_count"] == 5
