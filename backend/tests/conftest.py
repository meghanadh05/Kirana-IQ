"""Shared test fixtures.

Tests run against a real PostgreSQL instance (the same one docker compose
starts). Each test that writes data uses a unique SKU and cleans up after
itself, so the suite is safe to run against a database that already holds the
generated dataset.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import execute, init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def ensure_schema():
    init_db()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def unique_sku() -> str:
    return f"TEST-{uuid.uuid4().hex[:8].upper()}"


@pytest.fixture
def created_product(client: TestClient, unique_sku: str):
    """Create a product for the test and delete it afterwards."""
    payload = {
        "sku": unique_sku,
        "name": "Test Product 1L",
        "category": "Test Category",
        "unit_price": "42.50",
        "current_stock": 100,
        "reorder_level": 20,
        "lead_time_days": 3,
    }
    response = client.post("/products", json=payload)
    assert response.status_code == 201, response.text
    product = response.json()

    yield product

    execute("DELETE FROM products WHERE id = %s", (product["id"],))
