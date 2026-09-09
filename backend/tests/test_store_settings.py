"""Store profile, onboarding and per-store policy."""

from __future__ import annotations

import pytest

from app.services import policy as policy_service


def test_a_new_store_starts_at_step_one(client, store):
    assert store["store"]["onboarding_step"] == 1
    assert store["store"]["onboarding_completed"] is False


def test_onboarding_completes_at_the_final_step(client, store, headers):
    response = client.post(
        f"/stores/{store['id']}/onboarding", headers=headers, json={"step": 4}
    )
    assert response.json()["onboarding_completed"] is True


def test_intermediate_onboarding_steps_do_not_complete_it(client, store, headers):
    response = client.post(
        f"/stores/{store['id']}/onboarding", headers=headers, json={"step": 2}
    )
    assert response.json()["onboarding_step"] == 2
    assert response.json()["onboarding_completed"] is False


def test_an_out_of_range_step_is_rejected(client, store, headers):
    assert client.post(
        f"/stores/{store['id']}/onboarding", headers=headers, json={"step": 9}
    ).status_code == 422


def test_store_details_can_be_updated(client, store, headers):
    response = client.patch(
        f"/stores/{store['id']}",
        headers=headers,
        json={"name": "Renamed Store", "gst_number": "36ABCDE1234F1Z5", "business_type": "PHARMACY"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Store"
    assert response.json()["business_type"] == "PHARMACY"


def test_an_unknown_business_type_is_rejected(client, store, headers):
    response = client.patch(
        f"/stores/{store['id']}", headers=headers, json={"business_type": "CASINO"}
    )
    assert response.status_code == 422


def test_settings_are_seeded_from_the_global_defaults(client, headers):
    from app.config import get_settings

    settings = client.get("/stores/current/settings", headers=headers).json()
    defaults = get_settings()
    assert float(settings["safety_days"]) == defaults.safety_days
    assert float(settings["critical_cover_days"]) == defaults.critical_cover_days


def test_settings_can_be_changed_per_store(client, store, headers):
    response = client.patch(
        "/stores/current/settings",
        headers=headers,
        json={"safety_days": 7, "overstock_cover_days": "45.00", "low_stock_threshold": 25},
    )
    assert response.status_code == 200
    assert response.json()["safety_days"] == 7

    policy = policy_service.for_store(store["id"])
    assert policy.safety_days == 7
    assert policy.overstock_cover_days == 45.0
    assert policy.low_stock_threshold == 25


def test_one_stores_policy_does_not_affect_another(client, store, headers, new_user):
    """Thresholds are a shop's decision, not a deployment's."""
    client.patch("/stores/current/settings", headers=headers, json={"safety_days": 9})

    outsider = new_user()
    other = client.post("/stores", headers=outsider["headers"], json={"name": "Other"}).json()

    assert policy_service.for_store(store["id"]).safety_days == 9
    assert policy_service.for_store(other["id"]).safety_days != 9


@pytest.mark.parametrize(
    "field,value",
    [
        ("safety_days", -1),
        ("service_level_z", "9"),
        ("financial_year_start_month", 13),
        ("default_tax_rate", "150"),
        ("low_stock_threshold", -5),
    ],
)
def test_out_of_range_settings_are_rejected(client, headers, field, value):
    response = client.patch("/stores/current/settings", headers=headers, json={field: value})
    assert response.status_code == 422


def test_changed_thresholds_change_the_risk_verdict(client, headers, demo_headers):
    """Policy is not decoration: it must actually move the numbers."""
    before = client.get("/inventory/summary", headers=demo_headers).json()

    client.patch(
        "/stores/current/settings", headers=demo_headers, json={"critical_cover_days": "0.1"}
    )
    after = client.get("/inventory/summary", headers=demo_headers).json()

    client.patch(
        "/stores/current/settings", headers=demo_headers, json={"critical_cover_days": "2.0"}
    )
    assert after["critical_products"] <= before["critical_products"]
