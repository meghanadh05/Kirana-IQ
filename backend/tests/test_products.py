"""Product catalogue: validation, filtering, archiving and CSV."""

from __future__ import annotations

import io

import pytest


# --------------------------------------------------------------------------
# Creation and validation
# --------------------------------------------------------------------------


def test_create_product_returns_it(client, headers, product):
    assert product["id"] > 0
    assert product["current_stock"] == 100
    assert product["is_active"] is True


def test_opening_stock_is_recorded_in_the_ledger(client, headers, product):
    """Stock that appears without a movement is stock nobody can explain."""
    movements = client.get(
        "/inventory/movements", headers=headers, params={"product_id": product["id"]}
    ).json()["items"]

    assert len(movements) == 1
    assert movements[0]["type"] == "OPENING_STOCK"
    assert movements[0]["quantity_change"] == 100
    assert movements[0]["quantity_before"] == 0


def test_a_product_with_no_opening_stock_has_no_movement(client, headers, product_factory):
    product = product_factory(current_stock=0)
    movements = client.get(
        "/inventory/movements", headers=headers, params={"product_id": product["id"]}
    ).json()
    assert movements["total"] == 0


def test_duplicate_sku_in_the_same_store_is_a_conflict(client, headers, product):
    response = client.post(
        "/products",
        headers=headers,
        json={
            "sku": product["sku"],
            "name": "Another product",
            "category": "Test Category",
            "selling_price": "10.00",
        },
    )
    assert response.status_code == 409
    assert "SKU" in response.json()["detail"]


def test_duplicate_barcode_in_the_same_store_is_a_conflict(client, headers, product_factory):
    product_factory(barcode="8901234567890")
    response = client.post(
        "/products",
        headers=headers,
        json={
            "sku": "OTHER-SKU",
            "barcode": "8901234567890",
            "name": "Another product",
            "category": "Test Category",
            "selling_price": "10.00",
        },
    )
    assert response.status_code == 409
    assert "Barcode" in response.json()["detail"]


def test_many_products_may_have_no_barcode(client, headers, product_factory):
    """An empty barcode must be NULL, or the unique index collides on ''."""
    product_factory(barcode=None)
    product_factory(barcode="")
    product_factory()


@pytest.mark.parametrize(
    "field,value",
    [
        ("selling_price", "-1"),
        ("cost_price", "-1"),
        ("current_stock", -5),
        ("reorder_level", -1),
        ("tax_rate", "-2"),
        ("lead_time_days", -1),
        ("unit", "furlong"),
    ],
)
def test_invalid_field_values_are_rejected(client, headers, field, value):
    payload = {
        "sku": "BAD-1",
        "name": "Bad product",
        "category": "Test Category",
        "selling_price": "10.00",
        field: value,
    }
    assert client.post("/products", headers=headers, json=payload).status_code == 422


# --------------------------------------------------------------------------
# Reading, filtering and sorting
# --------------------------------------------------------------------------


def test_products_are_paginated(client, headers, product_factory):
    for _ in range(5):
        product_factory()

    page = client.get("/products", headers=headers, params={"limit": 2}).json()
    assert len(page["items"]) == 2
    assert page["total"] == 5
    assert page["limit"] == 2


def test_search_matches_name_sku_and_exact_barcode(client, headers, product_factory):
    target = product_factory(name="Amul Taaza Milk", sku="DRY-999", barcode="8909998887776")
    product_factory(name="Parle-G Biscuit")

    for term in ("Amul", "DRY-999", "8909998887776"):
        found = client.get("/products", headers=headers, params={"search": term}).json()
        assert [row["id"] for row in found["items"]] == [target["id"]], term


def test_stock_status_filters(client, headers, product_factory):
    out = product_factory(current_stock=0, reorder_level=10)
    low = product_factory(current_stock=5, reorder_level=10)
    healthy = product_factory(current_stock=100, reorder_level=10)

    def ids(status):
        return {
            row["id"]
            for row in client.get(
                "/products", headers=headers, params={"stock_status": status}
            ).json()["items"]
        }

    assert ids("out") == {out["id"]}
    assert ids("low") == {low["id"]}
    assert ids("in") == {healthy["id"]}


def test_category_filter(client, headers, product_factory):
    dairy = product_factory(category="Dairy")
    product_factory(category="Snacks")

    found = client.get("/products", headers=headers, params={"category": "Dairy"}).json()
    assert [row["id"] for row in found["items"]] == [dairy["id"]]


def test_sorting_by_stock_descending(client, headers, product_factory):
    product_factory(current_stock=5)
    product_factory(current_stock=90)

    rows = client.get(
        "/products", headers=headers, params={"sort": "stock", "direction": "desc"}
    ).json()["items"]
    assert [row["current_stock"] for row in rows] == [90, 5]


def test_an_unknown_sort_field_falls_back_rather_than_failing(client, headers, product):
    """The sort column is whitelisted, so an injected value cannot reach SQL."""
    response = client.get(
        "/products", headers=headers, params={"sort": "name; DROP TABLE products--"}
    )
    assert response.status_code == 200


def test_catalogue_stats_value_the_inventory(client, headers, product_factory):
    product_factory(current_stock=10, cost_price="20.00", selling_price="30.00")
    product_factory(current_stock=0, reorder_level=5)

    stats = client.get("/products/stats", headers=headers).json()
    assert stats["total"] == 2
    assert stats["out_of_stock"] == 1
    assert float(stats["inventory_cost_value"]) == 200.0
    assert float(stats["inventory_retail_value"]) == 300.0


def test_unknown_product_is_not_found(client, headers):
    assert client.get("/products/99999999", headers=headers).status_code == 404


# --------------------------------------------------------------------------
# Barcode lookup — the POS scan path
# --------------------------------------------------------------------------


def test_barcode_lookup_finds_the_product(client, headers, product_factory):
    product = product_factory(barcode="8901111111111")
    found = client.get("/products/barcode/8901111111111", headers=headers).json()
    assert found["id"] == product["id"]


def test_barcode_lookup_falls_back_to_sku(client, headers, product_factory):
    """A typed SKU arrives through the same input as a scanned barcode."""
    product = product_factory(sku="TYPED-001", barcode=None)
    found = client.get("/products/barcode/TYPED-001", headers=headers).json()
    assert found["id"] == product["id"]


def test_barcode_lookup_rejects_archived_products(client, headers, product_factory):
    product = product_factory(barcode="8902222222222")
    client.delete(f"/products/{product['id']}", headers=headers)

    response = client.get("/products/barcode/8902222222222", headers=headers)
    assert response.status_code == 422


def test_unknown_barcode_is_not_found(client, headers):
    assert client.get("/products/barcode/0000000000000", headers=headers).status_code == 404


# --------------------------------------------------------------------------
# Updating and archiving
# --------------------------------------------------------------------------


def test_update_changes_the_named_fields_only(client, headers, product):
    response = client.patch(
        f"/products/{product['id']}", headers=headers, json={"selling_price": "75.00"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert float(updated["selling_price"]) == 75.0
    assert updated["name"] == product["name"]


def test_stock_cannot_be_edited_through_the_product_form(client, headers, product):
    """Stock only moves through the ledger; a form field would bypass it."""
    client.patch(f"/products/{product['id']}", headers=headers, json={"current_stock": 5000})
    after = client.get(f"/products/{product['id']}", headers=headers).json()
    assert after["current_stock"] == product["current_stock"]


def test_archiving_hides_a_product_without_deleting_it(client, headers, product):
    client.delete(f"/products/{product['id']}", headers=headers)

    listed = client.get("/products", headers=headers).json()
    assert listed["total"] == 0

    with_archived = client.get(
        "/products", headers=headers, params={"include_archived": True}
    ).json()
    assert with_archived["total"] == 1
    assert with_archived["items"][0]["is_active"] is False


def test_updating_to_a_taken_sku_is_a_conflict(client, headers, product_factory):
    first = product_factory()
    second = product_factory()
    response = client.patch(
        f"/products/{second['id']}", headers=headers, json={"sku": first["sku"]}
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------
# CSV import and export
# --------------------------------------------------------------------------


def _upload(client, headers, content: str):
    return client.post(
        "/products/import",
        headers=headers,
        files={"file": ("products.csv", io.BytesIO(content.encode()), "text/csv")},
    )


def test_csv_import_creates_products(client, headers):
    csv_content = (
        "sku,name,category,selling_price,cost_price,current_stock,reorder_level\n"
        "IMP-1,Imported Milk,Dairy,33.00,27.00,40,10\n"
        "IMP-2,Imported Biscuit,Snacks,30.00,24.00,25,5\n"
    )
    result = _upload(client, headers, csv_content).json()
    assert result["created"] == 2
    assert result["failed"] == 0

    listed = client.get("/products", headers=headers).json()
    assert listed["total"] == 2


def test_csv_import_records_opening_stock_in_the_ledger(client, headers):
    _upload(
        client,
        headers,
        "sku,name,category,selling_price,current_stock\nIMP-3,Imported,Dairy,10.00,15\n",
    )
    movements = client.get("/inventory/movements", headers=headers).json()["items"]
    assert movements[0]["type"] == "OPENING_STOCK"
    assert movements[0]["quantity_after"] == 15


def test_csv_import_updates_existing_skus(client, headers, product_factory):
    existing = product_factory(sku="IMP-4", selling_price="10.00", current_stock=5)

    result = _upload(
        client,
        headers,
        "sku,name,category,selling_price,current_stock\nIMP-4,Renamed,Dairy,20.00,30\n",
    ).json()
    assert result["updated"] == 1

    after = client.get(f"/products/{existing['id']}", headers=headers).json()
    assert float(after["selling_price"]) == 20.0
    assert after["current_stock"] == 30


def test_csv_import_reports_bad_rows_without_losing_good_ones(client, headers):
    """A 500-row file must not be unusable because of one typo."""
    csv_content = (
        "sku,name,category,selling_price\n"
        "GOOD-1,Fine,Dairy,10.00\n"
        "BAD-1,Broken,Dairy,not-a-number\n"
        "GOOD-2,Also fine,Dairy,12.00\n"
    )
    result = _upload(client, headers, csv_content).json()

    assert result["created"] == 2
    assert result["failed"] == 1
    assert result["errors"][0]["row"] == 3
    assert result["errors"][0]["sku"] == "BAD-1"


def test_csv_import_requires_the_mandatory_columns(client, headers):
    response = _upload(client, headers, "sku,name\nX-1,No price\n")
    assert response.status_code == 422
    assert "selling_price" in response.json()["detail"]


def test_csv_export_round_trips(client, headers, product_factory):
    product_factory(sku="EXP-1", name="Exported")

    exported = client.get("/products/export", headers=headers)
    assert exported.headers["content-type"].startswith("text/csv")
    assert "EXP-1" in exported.text
    assert "selling_price" in exported.text


# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------


def test_creating_a_product_registers_its_category(client, headers, product_factory):
    product_factory(category="Beverages")
    names = {row["name"] for row in client.get("/categories", headers=headers).json()}
    assert "Beverages" in names


def test_categories_report_their_product_count(client, headers, product_factory):
    product_factory(category="Dairy")
    product_factory(category="Dairy")

    dairy = next(
        row for row in client.get("/categories", headers=headers).json() if row["name"] == "Dairy"
    )
    assert dairy["product_count"] == 2


def test_a_category_in_use_cannot_be_deleted(client, headers, product_factory):
    product_factory(category="Dairy")
    dairy = next(
        row for row in client.get("/categories", headers=headers).json() if row["name"] == "Dairy"
    )
    response = client.delete(f"/categories/{dairy['id']}", headers=headers)
    assert response.status_code == 409


def test_an_empty_category_can_be_deleted(client, headers):
    created = client.post(
        "/categories", headers=headers, json={"name": "Temporary"}
    ).json()
    assert client.delete(f"/categories/{created['id']}", headers=headers).status_code == 200


def test_duplicate_category_is_a_conflict(client, headers):
    client.post("/categories", headers=headers, json={"name": "Dairy"})
    response = client.post("/categories", headers=headers, json={"name": "Dairy"})
    assert response.status_code == 409
