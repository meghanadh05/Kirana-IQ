"""Multi-tenancy and role authorisation.

These are the tests that matter most: a bug here leaks one shop's business to
another. Every one of them asserts on real HTTP responses rather than on an
internal helper, because the guarantee is about the API surface.
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------
# Store isolation
# --------------------------------------------------------------------------


def test_a_new_account_sees_no_stores(client, new_user):
    account = new_user()
    assert client.get("/stores", headers=account["headers"]).json() == []


def test_store_creator_becomes_its_owner(client, store):
    members = client.get(f"/stores/{store['id']}/members", headers=store["headers"]).json()
    assert len(members) == 1
    assert members[0]["role"] == "OWNER"


def test_another_users_store_is_forbidden(client, store, new_user):
    """403, not 404: whether the store exists is not the caller's business."""
    outsider = new_user()
    response = client.get(f"/stores/{store['id']}", headers=outsider["headers"])
    assert response.status_code == 403


def test_products_are_invisible_across_stores(client, store, product, new_user):
    outsider = new_user()
    own = client.post(
        "/stores", headers=outsider["headers"], json={"name": "Outsider Store"}
    ).json()
    outsider_headers = {**outsider["headers"], "X-Store-Id": str(own["id"])}

    listed = client.get("/products", headers=outsider_headers).json()
    assert listed["total"] == 0

    direct = client.get(f"/products/{product['id']}", headers=outsider_headers)
    assert direct.status_code == 404


def test_store_id_header_is_validated_against_membership(client, store, new_user):
    """Naming someone else's store in the header must not grant access."""
    outsider = new_user()
    client.post("/stores", headers=outsider["headers"], json={"name": "Outsider Store"})

    forged = {**outsider["headers"], "X-Store-Id": str(store["id"])}
    for path in ("/products", "/sales", "/inventory", "/dashboard", "/suppliers"):
        assert client.get(path, headers=forged).status_code == 403, path


def test_sales_are_invisible_across_stores(client, store, product, new_user):
    client.post(
        "/pos/checkout",
        headers=store["headers"],
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
    )

    outsider = new_user()
    own = client.post("/stores", headers=outsider["headers"], json={"name": "Other"}).json()
    outsider_headers = {**outsider["headers"], "X-Store-Id": str(own["id"])}

    assert client.get("/sales", headers=outsider_headers).json()["total"] == 0


def test_search_only_returns_the_callers_store(client, store, product, new_user):
    outsider = new_user()
    own = client.post("/stores", headers=outsider["headers"], json={"name": "Other"}).json()
    outsider_headers = {**outsider["headers"], "X-Store-Id": str(own["id"])}

    results = client.get(
        "/search", headers=outsider_headers, params={"q": product["name"]}
    ).json()
    assert results["products"] == []


def test_inventory_adjustment_cannot_reach_another_store(client, store, product, new_user):
    outsider = new_user()
    own = client.post("/stores", headers=outsider["headers"], json={"name": "Other"}).json()
    outsider_headers = {**outsider["headers"], "X-Store-Id": str(own["id"])}

    response = client.post(
        "/inventory/adjustments",
        headers=outsider_headers,
        json={"product_id": product["id"], "quantity_change": -5, "reason": "DAMAGE"},
    )
    assert response.status_code == 404

    # And the real store's stock is untouched.
    unchanged = client.get(f"/products/{product['id']}", headers=store["headers"]).json()
    assert unchanged["current_stock"] == product["current_stock"]


def test_checkout_cannot_sell_another_stores_product(client, store, product, new_user):
    outsider = new_user()
    own = client.post("/stores", headers=outsider["headers"], json={"name": "Other"}).json()
    outsider_headers = {**outsider["headers"], "X-Store-Id": str(own["id"])}

    response = client.post(
        "/pos/checkout",
        headers=outsider_headers,
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert response.status_code == 404


def test_skus_may_repeat_across_stores(client, store, new_user):
    """Two shops can stock the same product under the same code."""
    payload = {
        "sku": "SHARED-SKU-001",
        "name": "Amul Milk 1L",
        "category": "Dairy",
        "selling_price": "33.00",
    }
    assert client.post("/products", headers=store["headers"], json=payload).status_code == 201

    outsider = new_user()
    own = client.post("/stores", headers=outsider["headers"], json={"name": "Other"}).json()
    outsider_headers = {**outsider["headers"], "X-Store-Id": str(own["id"])}
    assert client.post("/products", headers=outsider_headers, json=payload).status_code == 201


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------


def test_cashier_can_use_the_till(client, store, product, member_factory):
    cashier = member_factory("CASHIER")
    response = client.post(
        "/pos/checkout",
        headers=cashier["headers"],
        json={"items": [{"product_id": product["id"], "quantity": 2}]},
    )
    assert response.status_code == 201


def test_cashier_can_look_products_up(client, store, product, member_factory):
    cashier = member_factory("CASHIER")
    assert client.get("/products", headers=cashier["headers"]).status_code == 200
    assert client.get("/sales", headers=cashier["headers"]).status_code == 200


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("post", "/products", {"sku": "X1", "name": "X", "category": "C", "selling_price": "1"}),
        ("post", "/suppliers", {"name": "S"}),
        ("post", "/expenses", {"category": "Rent", "amount": "100", "expense_date": "2026-01-01"}),
    ],
)
def test_cashier_cannot_manage_the_catalogue(client, member_factory, method, path, payload):
    cashier = member_factory("CASHIER")
    response = getattr(client, method)(path, headers=cashier["headers"], json=payload)
    assert response.status_code == 403


def test_cashier_cannot_adjust_stock(client, store, product, member_factory):
    cashier = member_factory("CASHIER")
    response = client.post(
        "/inventory/adjustments",
        headers=cashier["headers"],
        json={"product_id": product["id"], "quantity_change": 500, "reason": "COUNT_CORRECTION"},
    )
    assert response.status_code == 403


def test_cashier_cannot_cancel_a_sale(client, store, product, member_factory):
    cashier = member_factory("CASHIER")
    sale = client.post(
        "/pos/checkout",
        headers=store["headers"],
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
    ).json()

    response = client.post(
        f"/sales/{sale['id']}/cancel", headers=cashier["headers"], json={"reason": "oops"}
    )
    assert response.status_code == 403


def test_manager_can_manage_the_catalogue(client, member_factory):
    manager = member_factory("MANAGER")
    response = client.post(
        "/products",
        headers=manager["headers"],
        json={"sku": "MGR-1", "name": "Managed", "category": "C", "selling_price": "10"},
    )
    assert response.status_code == 201


def test_manager_cannot_change_store_policy(client, store, member_factory):
    """Thresholds change what every forecast says, so they are an owner decision."""
    manager = member_factory("MANAGER")
    response = client.patch(
        "/stores/current/settings", headers=manager["headers"], json={"safety_days": 9}
    )
    assert response.status_code == 403


def test_manager_cannot_invite_members(client, store, member_factory, new_user):
    manager = member_factory("MANAGER")
    outsider = new_user()
    response = client.post(
        f"/stores/{store['id']}/members",
        headers=manager["headers"],
        json={"email": outsider["email"], "role": "CASHIER"},
    )
    assert response.status_code == 403


def test_owner_can_change_a_members_role(client, store, member_factory):
    cashier = member_factory("CASHIER")
    response = client.patch(
        f"/stores/{store['id']}/members/{cashier['user']['id']}",
        headers=store["headers"],
        json={"role": "MANAGER"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "MANAGER"


def test_the_last_owner_cannot_be_demoted(client, store):
    """A store with no owner can never be administered again."""
    owner_id = store["owner"]["user"]["id"]
    response = client.patch(
        f"/stores/{store['id']}/members/{owner_id}",
        headers=store["headers"],
        json={"role": "CASHIER"},
    )
    assert response.status_code == 409


def test_the_last_owner_cannot_be_removed(client, store):
    owner_id = store["owner"]["user"]["id"]
    response = client.delete(
        f"/stores/{store['id']}/members/{owner_id}", headers=store["headers"]
    )
    assert response.status_code == 409


def test_removed_member_loses_access_immediately(client, store, member_factory):
    manager = member_factory("MANAGER")
    assert client.get("/products", headers=manager["headers"]).status_code == 200

    client.delete(
        f"/stores/{store['id']}/members/{manager['user']['id']}", headers=store["headers"]
    )
    assert client.get("/products", headers=manager["headers"]).status_code == 403


def test_inviting_an_unregistered_address_reports_not_found(client, store):
    response = client.post(
        f"/stores/{store['id']}/members",
        headers=store["headers"],
        json={"email": "nobody-at-all@kiranaiq-tests.com", "role": "CASHIER"},
    )
    assert response.status_code == 404
