"""Product endpoint tests."""

from __future__ import annotations

from app.database import execute


def test_create_product_returns_201_with_id(client, unique_sku):
    response = client.post(
        "/products",
        json={
            "sku": unique_sku,
            "name": "Fresh Milk 1L",
            "category": "Dairy",
            "unit_price": "33.00",
            "current_stock": 50,
            "reorder_level": 20,
            "lead_time_days": 2,
        },
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["id"] > 0
    assert body["sku"] == unique_sku
    assert float(body["unit_price"]) == 33.00

    execute("DELETE FROM products WHERE id = %s", (body["id"],))


def test_get_product_by_id(client, created_product):
    response = client.get(f"/products/{created_product['id']}")
    assert response.status_code == 200
    assert response.json()["sku"] == created_product["sku"]


def test_get_missing_product_returns_404(client):
    response = client.get("/products/99999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_product_with_non_integer_id_returns_422(client):
    assert client.get("/products/not-a-number").status_code == 422


def test_duplicate_sku_returns_409(client, created_product):
    response = client.post(
        "/products",
        json={
            "sku": created_product["sku"],
            "name": "Duplicate",
            "category": "Dairy",
            "unit_price": "10.00",
        },
    )
    assert response.status_code == 409


def test_negative_price_is_rejected(client, unique_sku):
    response = client.post(
        "/products",
        json={"sku": unique_sku, "name": "Bad", "category": "Dairy", "unit_price": "-5.00"},
    )
    assert response.status_code == 422


def test_negative_stock_is_rejected(client, unique_sku):
    response = client.post(
        "/products",
        json={
            "sku": unique_sku,
            "name": "Bad",
            "category": "Dairy",
            "unit_price": "5.00",
            "current_stock": -1,
        },
    )
    assert response.status_code == 422


def test_list_products_returns_seeded_catalogue(client):
    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) > 0
    assert {"id", "sku", "name", "category", "current_stock"} <= set(products[0])


def test_list_products_filters_by_category(client, created_product):
    response = client.get("/products", params={"category": created_product["category"]})
    assert response.status_code == 200
    returned = response.json()
    assert returned, "expected at least the fixture product"
    assert all(p["category"] == created_product["category"] for p in returned)


def test_list_products_search_matches_sku(client, created_product):
    response = client.get("/products", params={"search": created_product["sku"]})
    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [created_product["id"]]


def test_list_products_respects_limit(client):
    response = client.get("/products", params={"limit": 3})
    assert response.status_code == 200
    assert len(response.json()) <= 3


def test_invalid_limit_is_rejected(client):
    assert client.get("/products", params={"limit": 0}).status_code == 422


def test_categories_endpoint_returns_sorted_unique_list(client):
    response = client.get("/products/categories")
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) == len(set(categories))
    assert categories == sorted(categories)
