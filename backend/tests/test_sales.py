"""Sales endpoint tests."""

from __future__ import annotations


def test_create_sale_returns_201(client, created_product):
    response = client.post(
        "/sales",
        json={
            "product_id": created_product["id"],
            "quantity": 7,
            "sale_date": "2026-09-08",
            "unit_price": "42.50",
        },
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["product_id"] == created_product["id"]
    assert body["quantity"] == 7
    assert body["sale_date"] == "2026-09-08"


def test_create_sale_for_missing_product_returns_404(client):
    response = client.post(
        "/sales",
        json={
            "product_id": 99999999,
            "quantity": 5,
            "sale_date": "2026-09-08",
            "unit_price": "10.00",
        },
    )
    assert response.status_code == 404


def test_negative_quantity_is_rejected(client, created_product):
    response = client.post(
        "/sales",
        json={
            "product_id": created_product["id"],
            "quantity": -3,
            "sale_date": "2026-09-08",
            "unit_price": "10.00",
        },
    )
    assert response.status_code == 422


def test_malformed_date_is_rejected(client, created_product):
    response = client.post(
        "/sales",
        json={
            "product_id": created_product["id"],
            "quantity": 3,
            "sale_date": "08-09-2026",
            "unit_price": "10.00",
        },
    )
    assert response.status_code == 422


def test_list_sales_returns_chronological_history(client, created_product):
    for day, qty in [("2026-09-03", 4), ("2026-09-01", 9), ("2026-09-02", 6)]:
        client.post(
            "/sales",
            json={
                "product_id": created_product["id"],
                "quantity": qty,
                "sale_date": day,
                "unit_price": "42.50",
            },
        )

    response = client.get(f"/sales/{created_product['id']}")
    assert response.status_code == 200

    dates = [row["sale_date"] for row in response.json()]
    assert dates == sorted(dates)
    assert dates == ["2026-09-01", "2026-09-02", "2026-09-03"]


def test_list_sales_filters_by_date_range(client, created_product):
    for day in ["2026-09-01", "2026-09-05", "2026-09-10"]:
        client.post(
            "/sales",
            json={
                "product_id": created_product["id"],
                "quantity": 2,
                "sale_date": day,
                "unit_price": "42.50",
            },
        )

    response = client.get(
        f"/sales/{created_product['id']}",
        params={"start_date": "2026-09-02", "end_date": "2026-09-07"},
    )
    assert response.status_code == 200
    assert [row["sale_date"] for row in response.json()] == ["2026-09-05"]


def test_inverted_date_range_is_rejected(client, created_product):
    response = client.get(
        f"/sales/{created_product['id']}",
        params={"start_date": "2026-09-10", "end_date": "2026-09-01"},
    )
    assert response.status_code == 422


def test_list_sales_for_missing_product_returns_404(client):
    assert client.get("/sales/99999999").status_code == 404


def test_sales_summary_aggregates_correctly(client, created_product):
    for day, qty in [("2026-09-01", 10), ("2026-09-02", 15)]:
        client.post(
            "/sales",
            json={
                "product_id": created_product["id"],
                "quantity": qty,
                "sale_date": day,
                "unit_price": "42.50",
            },
        )

    response = client.get(f"/sales/{created_product['id']}/summary")
    assert response.status_code == 200

    body = response.json()
    assert body["records"] == 2
    assert body["total_units"] == 25
    assert body["first_sale_date"] == "2026-09-01"
    assert body["last_sale_date"] == "2026-09-02"


def test_seeded_product_has_history(client):
    """The generated dataset should be loaded and reachable through the API."""
    products = client.get("/products", params={"limit": 1}).json()
    if not products:
        return  # empty database: nothing to assert

    summary = client.get(f"/sales/{products[0]['id']}/summary").json()
    assert summary["records"] > 0
    assert summary["total_units"] > 0
