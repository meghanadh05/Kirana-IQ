"""Suppliers, purchase orders, receiving and the reorder integration."""

from __future__ import annotations

from decimal import Decimal

import pytest


# --------------------------------------------------------------------------
# Suppliers
# --------------------------------------------------------------------------


def test_create_and_read_a_supplier(client, headers, supplier):
    detail = client.get(f"/suppliers/{supplier['id']}", headers=headers).json()
    assert detail["name"] == "Test Supplier"
    assert detail["products"] == []
    assert detail["purchase_orders"] == []
    assert detail["total_purchased"] == 0


def test_supplier_lists_the_products_it_supplies(client, headers, supplier, product_factory):
    product = product_factory(supplier_id=supplier["id"])
    detail = client.get(f"/suppliers/{supplier['id']}", headers=headers).json()
    assert [row["product_id"] for row in detail["products"]] == [product["id"]]


def test_supplier_search(client, headers):
    client.post("/suppliers", headers=headers, json={"name": "Amul Distributors"})
    client.post("/suppliers", headers=headers, json={"name": "Britannia Agency"})

    found = client.get("/suppliers", headers=headers, params={"search": "Amul"}).json()
    assert [row["name"] for row in found] == ["Amul Distributors"]


def test_archiving_a_supplier_hides_it(client, headers, supplier):
    client.delete(f"/suppliers/{supplier['id']}", headers=headers)
    assert client.get("/suppliers", headers=headers).json() == []

    with_inactive = client.get(
        "/suppliers", headers=headers, params={"include_inactive": True}
    ).json()
    assert len(with_inactive) == 1


def test_unknown_supplier_is_not_found(client, headers):
    assert client.get("/suppliers/99999999", headers=headers).status_code == 404


# --------------------------------------------------------------------------
# Creating purchase orders
# --------------------------------------------------------------------------


def _order(client, headers, supplier, product, quantity=20, **extra):
    return client.post(
        "/purchase-orders",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "items": [{"product_id": product["id"], "quantity": quantity}],
            **extra,
        },
    )


def test_purchase_order_defaults_to_a_draft(client, headers, supplier, product):
    response = _order(client, headers, supplier, product)
    assert response.status_code == 201, response.text

    order = response.json()
    assert order["status"] == "DRAFT"
    assert order["po_number"] == "PO-0001"
    assert order["item_count"] == 1
    assert order["unit_count"] == 20


def test_line_cost_defaults_to_the_product_cost_price(client, headers, supplier, product):
    order = _order(client, headers, supplier, product, quantity=10).json()
    assert Decimal(order["items"][0]["cost_price"]) == Decimal("30.00")
    assert Decimal(order["subtotal"]) == Decimal("300.00")


def test_line_cost_can_be_overridden(client, headers, supplier, product):
    response = client.post(
        "/purchase-orders",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "items": [{"product_id": product["id"], "quantity": 10, "cost_price": "25.00"}],
        },
    )
    assert Decimal(response.json()["subtotal"]) == Decimal("250.00")


def test_an_empty_purchase_order_is_rejected(client, headers, supplier):
    response = client.post(
        "/purchase-orders", headers=headers, json={"supplier_id": supplier["id"], "items": []}
    )
    assert response.status_code == 422


def test_ordering_an_unknown_product_is_not_found(client, headers, supplier):
    response = client.post(
        "/purchase-orders",
        headers=headers,
        json={"supplier_id": supplier["id"], "items": [{"product_id": 99999999, "quantity": 1}]},
    )
    assert response.status_code == 404


def test_an_unknown_supplier_is_not_found(client, headers, product):
    response = client.post(
        "/purchase-orders",
        headers=headers,
        json={"supplier_id": 99999999, "items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert response.status_code == 404


def test_purchase_orders_can_be_filtered_by_status(client, headers, supplier, product):
    draft = _order(client, headers, supplier, product).json()
    ordered = _order(client, headers, supplier, product).json()
    client.patch(
        f"/purchase-orders/{ordered['id']}/status", headers=headers, json={"status": "ORDERED"}
    )

    found = client.get("/purchase-orders", headers=headers, params={"status": "DRAFT"}).json()
    assert [row["id"] for row in found["items"]] == [draft["id"]]


# --------------------------------------------------------------------------
# Status transitions
# --------------------------------------------------------------------------


def test_a_draft_can_be_ordered(client, headers, supplier, product):
    order = _order(client, headers, supplier, product).json()
    response = client.patch(
        f"/purchase-orders/{order['id']}/status", headers=headers, json={"status": "ORDERED"}
    )
    assert response.json()["status"] == "ORDERED"


def test_a_cancelled_order_cannot_be_reopened(client, headers, supplier, product):
    order = _order(client, headers, supplier, product).json()
    client.patch(
        f"/purchase-orders/{order['id']}/status", headers=headers, json={"status": "CANCELLED"}
    )
    response = client.patch(
        f"/purchase-orders/{order['id']}/status", headers=headers, json={"status": "ORDERED"}
    )
    assert response.status_code == 409


def test_a_draft_cannot_jump_straight_to_received(client, headers, supplier, product):
    order = _order(client, headers, supplier, product).json()
    response = client.patch(
        f"/purchase-orders/{order['id']}/status", headers=headers, json={"status": "RECEIVED"}
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------
# Receiving
# --------------------------------------------------------------------------


def _ordered(client, headers, supplier, product, quantity=20):
    order = _order(client, headers, supplier, product, quantity=quantity).json()
    client.patch(
        f"/purchase-orders/{order['id']}/status", headers=headers, json={"status": "ORDERED"}
    )
    return client.get(f"/purchase-orders/{order['id']}", headers=headers).json()


def test_receiving_increases_stock(client, headers, supplier, product):
    order = _ordered(client, headers, supplier, product, quantity=20)
    received = client.post(
        f"/purchase-orders/{order['id']}/receive", headers=headers, json={}
    ).json()

    assert received["status"] == "RECEIVED"
    after = client.get(f"/products/{product['id']}", headers=headers).json()
    assert after["current_stock"] == 120


def test_receiving_writes_a_ledger_entry(client, headers, supplier, product):
    order = _ordered(client, headers, supplier, product, quantity=20)
    client.post(f"/purchase-orders/{order['id']}/receive", headers=headers, json={})

    movements = client.get(
        "/inventory/movements", headers=headers, params={"type": "PURCHASE"}
    ).json()["items"]
    assert movements[0]["quantity_change"] == 20
    assert movements[0]["reference_type"] == "PURCHASE_ORDER"
    assert movements[0]["reference_id"] == order["id"]


def test_partial_receipt_leaves_the_order_open(client, headers, supplier, product):
    order = _ordered(client, headers, supplier, product, quantity=20)
    item_id = order["items"][0]["id"]

    partial = client.post(
        f"/purchase-orders/{order['id']}/receive",
        headers=headers,
        json={"items": [{"item_id": item_id, "quantity": 5}]},
    ).json()

    assert partial["status"] == "PARTIALLY_RECEIVED"
    assert partial["received_count"] == 5
    assert client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"] == 105


def test_receiving_the_remainder_completes_the_order(client, headers, supplier, product):
    order = _ordered(client, headers, supplier, product, quantity=20)
    item_id = order["items"][0]["id"]

    client.post(
        f"/purchase-orders/{order['id']}/receive",
        headers=headers,
        json={"items": [{"item_id": item_id, "quantity": 5}]},
    )
    final = client.post(
        f"/purchase-orders/{order['id']}/receive", headers=headers, json={}
    ).json()

    assert final["status"] == "RECEIVED"
    assert final["received_count"] == 20
    assert client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"] == 120


def test_receiving_more_than_was_ordered_is_rejected(client, headers, supplier, product):
    order = _ordered(client, headers, supplier, product, quantity=20)
    response = client.post(
        f"/purchase-orders/{order['id']}/receive",
        headers=headers,
        json={"items": [{"item_id": order["items"][0]["id"], "quantity": 50}]},
    )
    assert response.status_code == 422
    assert client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"] == 100


def test_a_draft_cannot_be_received(client, headers, supplier, product):
    order = _order(client, headers, supplier, product).json()
    response = client.post(f"/purchase-orders/{order['id']}/receive", headers=headers, json={})
    assert response.status_code == 409
    assert "draft" in response.json()["detail"].lower()


def test_a_cancelled_order_cannot_be_received(client, headers, supplier, product):
    order = _order(client, headers, supplier, product).json()
    client.patch(
        f"/purchase-orders/{order['id']}/status", headers=headers, json={"status": "CANCELLED"}
    )
    response = client.post(f"/purchase-orders/{order['id']}/receive", headers=headers, json={})
    assert response.status_code == 409


def test_an_order_cannot_be_received_twice(client, headers, supplier, product):
    order = _ordered(client, headers, supplier, product)
    client.post(f"/purchase-orders/{order['id']}/receive", headers=headers, json={})

    again = client.post(f"/purchase-orders/{order['id']}/receive", headers=headers, json={})
    assert again.status_code == 409
    assert client.get(f"/products/{product['id']}", headers=headers).json()["current_stock"] == 120


def test_receiving_updates_the_catalogue_cost_price(client, headers, supplier, product):
    """A delivery is the freshest evidence of what a product costs."""
    order = client.post(
        "/purchase-orders",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "items": [{"product_id": product["id"], "quantity": 10, "cost_price": "35.50"}],
        },
    ).json()
    client.patch(
        f"/purchase-orders/{order['id']}/status", headers=headers, json={"status": "ORDERED"}
    )
    client.post(f"/purchase-orders/{order['id']}/receive", headers=headers, json={})

    after = client.get(f"/products/{product['id']}", headers=headers).json()
    assert Decimal(after["cost_price"]) == Decimal("35.50")


def test_supplier_totals_follow_received_orders(client, headers, supplier, product):
    order = _ordered(client, headers, supplier, product, quantity=10)
    client.post(f"/purchase-orders/{order['id']}/receive", headers=headers, json={})

    detail = client.get(f"/suppliers/{supplier['id']}", headers=headers).json()
    assert detail["total_purchased"] == float(order["total"])
    assert detail["open_orders"] == 0


# --------------------------------------------------------------------------
# Reorder recommendations become purchase orders
# --------------------------------------------------------------------------


def test_suggestions_group_by_supplier(client, demo_headers):
    suggestions = client.get("/purchase-orders/suggestions", headers=demo_headers).json()
    if not suggestions["groups"]:
        pytest.skip("demo store has nothing to reorder")

    supplier_ids = [group["supplier_id"] for group in suggestions["groups"]]
    assert len(supplier_ids) == len(set(supplier_ids))

    for group in suggestions["groups"]:
        assert group["product_count"] == len(group["items"])
        assert group["total_units"] == sum(
            item["recommended_reorder_quantity"] for item in group["items"]
        )


def test_a_suggestion_becomes_a_draft_purchase_order(client, demo_headers):
    suggestions = client.get("/purchase-orders/suggestions", headers=demo_headers).json()
    group = next((g for g in suggestions["groups"] if g["supplier_id"]), None)
    if group is None:
        pytest.skip("demo store has no supplier-assigned reorders")

    response = client.post(
        "/purchase-orders/from-recommendations",
        headers=demo_headers,
        json={"supplier_id": group["supplier_id"]},
    )
    assert response.status_code == 201, response.text

    order = response.json()
    assert order["status"] == "DRAFT"
    assert order["supplier_id"] == group["supplier_id"]
    assert order["item_count"] > 0

    # The quantities are the ones the model recommended, not something invented.
    recommended = {
        item["product_id"]: item["recommended_reorder_quantity"] for item in group["items"]
    }
    for line in order["items"]:
        assert line["quantity"] == recommended[line["product_id"]]

    client.patch(
        f"/purchase-orders/{order['id']}/status",
        headers=demo_headers,
        json={"status": "CANCELLED"},
    )


def test_reordering_a_well_stocked_product_is_rejected(client, demo_headers):
    healthy = [
        row
        for row in client.get("/inventory/recommendations", headers=demo_headers).json()
        if row["recommended_reorder_quantity"] == 0
    ]
    if not healthy:
        pytest.skip("every demo product needs reordering")

    response = client.post(
        "/purchase-orders/from-recommendations",
        headers=demo_headers,
        json={"product_ids": [healthy[0]["product_id"]]},
    )
    assert response.status_code == 422
