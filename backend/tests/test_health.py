"""Tests for the system endpoints available in phase 1."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_expected_shape():
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["app"] == "Kirana-IQ"
    assert body["database"] in {"connected", "unavailable"}


def test_root_points_at_docs():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"
