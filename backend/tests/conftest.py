"""Shared test fixtures.

Tests run against a real PostgreSQL instance (the same one docker compose
starts). Multi-tenancy makes isolation easy: most tests get their own freshly
created store, so they cannot collide with each other or with a database that
already holds the demo dataset.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.database import execute, init_db, query_one
from app.main import app
from app.models import store as store_model


TEST_EMAIL_DOMAIN = "@kiranaiq-tests.com"


@pytest.fixture(scope="session", autouse=True)
def ensure_schema():
    init_db()
    yield
    # A catch-all sweep. Individual fixtures clean up after themselves, but a
    # few tests register accounts directly to assert on the endpoint, and the
    # suite is often pointed at the same database used for development.
    execute(
        "DELETE FROM stores WHERE id IN ("
        "  SELECT m.store_id FROM store_members m"
        "  JOIN users u ON u.id = m.user_id"
        "  WHERE u.email LIKE %s)",
        (f"%{TEST_EMAIL_DOMAIN}",),
    )
    execute("DELETE FROM users WHERE email LIKE %s", (f"%{TEST_EMAIL_DOMAIN}",))


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


def _unique_email(label: str = "user") -> str:
    return f"{label}-{uuid.uuid4().hex[:10]}{TEST_EMAIL_DOMAIN}"


@pytest.fixture(scope="session")
def owner(client: TestClient) -> dict[str, Any]:
    """A registered account reused across the suite. Stores are per-test.

    Removed afterwards so a suite run leaves no residue in a database that is
    also being used for development.
    """
    email = _unique_email("owner")
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "test-password-123", "full_name": "Test Owner"},
    )
    assert response.status_code == 201, response.text
    body = response.json()

    yield {
        "email": email,
        "password": "test-password-123",
        "token": body["access_token"],
        "user": body["user"],
    }

    # Stores this account still owns cascade away with the membership rows.
    execute(
        "DELETE FROM stores WHERE id IN "
        "(SELECT store_id FROM store_members WHERE user_id = %s)",
        (body["user"]["id"],),
    )
    execute("DELETE FROM users WHERE id = %s", (body["user"]["id"],))


@pytest.fixture
def new_user(client: TestClient):
    """Factory for extra accounts, for tenancy and role tests."""
    created: list[int] = []

    def _create(role_label: str = "other") -> dict[str, Any]:
        email = _unique_email(role_label)
        response = client.post(
            "/auth/register",
            json={"email": email, "password": "test-password-123", "full_name": "Other User"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        created.append(body["user"]["id"])
        return {
            "email": email,
            "password": "test-password-123",
            "token": body["access_token"],
            "user": body["user"],
            "headers": {"Authorization": f"Bearer {body['access_token']}"},
        }

    yield _create

    for user_id in created:
        # Stores created during the test outlive their creator otherwise:
        # stores.created_by is SET NULL, so only the membership links them.
        execute(
            "DELETE FROM stores WHERE id IN "
            "(SELECT store_id FROM store_members WHERE user_id = %s)",
            (user_id,),
        )
        execute("DELETE FROM users WHERE id = %s", (user_id,))


@pytest.fixture
def store(client: TestClient, owner: dict[str, Any]):
    """A fresh store owned by the session account, removed afterwards."""
    auth = {"Authorization": f"Bearer {owner['token']}"}
    response = client.post(
        "/stores",
        headers=auth,
        json={"name": f"Test Store {uuid.uuid4().hex[:6]}", "city": "Hyderabad"},
    )
    assert response.status_code == 201, response.text
    created = response.json()

    context = {
        "id": created["id"],
        "store": created,
        "owner": owner,
        "headers": {**auth, "X-Store-Id": str(created["id"])},
    }
    yield context

    # Cascades through products, sales, ledger, purchases and settings.
    execute("DELETE FROM stores WHERE id = %s", (created["id"],))


@pytest.fixture
def headers(store: dict[str, Any]) -> dict[str, str]:
    return store["headers"]


@pytest.fixture
def product_factory(client: TestClient, headers: dict[str, str]):
    """Create products in the test's store with sensible defaults."""
    counter = {"n": 0}

    def _create(**overrides: Any) -> dict[str, Any]:
        counter["n"] += 1
        payload = {
            "sku": f"SKU-{uuid.uuid4().hex[:8].upper()}",
            "name": f"Test Product {counter['n']}",
            "category": "Test Category",
            "selling_price": "50.00",
            "cost_price": "30.00",
            "tax_rate": "5.00",
            "current_stock": 100,
            "reorder_level": 20,
            "lead_time_days": 3,
            "unit": "piece",
        }
        payload.update(overrides)
        response = client.post("/products", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture
def product(product_factory) -> dict[str, Any]:
    return product_factory()


@pytest.fixture
def supplier(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.post(
        "/suppliers",
        headers=headers,
        json={"name": "Test Supplier", "phone": "9876500000", "default_lead_time_days": 4},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def member_factory(client: TestClient, store: dict[str, Any], new_user):
    """Add another account to the test's store with a given role."""

    def _add(role: str) -> dict[str, Any]:
        account = new_user(role.lower())
        response = client.post(
            f"/stores/{store['id']}/members",
            headers=store["headers"],
            json={"email": account["email"], "role": role},
        )
        assert response.status_code == 201, response.text
        account["headers"] = {
            "Authorization": f"Bearer {account['token']}",
            "X-Store-Id": str(store["id"]),
        }
        return account

    return _add


@pytest.fixture(scope="session")
def demo_store_id() -> int | None:
    """The seeded demo store, when the database has one.

    Tests that need a trained model and a year of history use it and skip
    otherwise, so a fresh clone still runs the rest of the suite.
    """
    row = query_one("SELECT id FROM stores WHERE is_demo = TRUE ORDER BY id LIMIT 1")
    return int(row["id"]) if row else None


@pytest.fixture
def demo_headers(client: TestClient, demo_store_id, owner) -> dict[str, str]:
    """Read-only access to the demo store for the session account."""
    if demo_store_id is None:
        pytest.skip("no demo store; run scripts/seed_demo.py")

    store_model.add_member(demo_store_id, owner["user"]["id"], "OWNER")
    yield {
        "Authorization": f"Bearer {owner['token']}",
        "X-Store-Id": str(demo_store_id),
    }
    store_model.remove_member(demo_store_id, owner["user"]["id"])
