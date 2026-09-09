"""Authentication tests."""

from __future__ import annotations

import uuid

import pytest

from app.security import hash_password, verify_password


def _email() -> str:
    return f"auth-{uuid.uuid4().hex[:10]}@kiranaiq-tests.com"


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------


def test_password_hash_is_not_the_password():
    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery"
    assert hashed.startswith("$2")


def test_password_verification_round_trip():
    hashed = hash_password("correct horse battery")
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong password", hashed)


def test_hashes_are_salted():
    """Two users with the same password must not share a hash."""
    assert hash_password("same-password") != hash_password("same-password")


def test_invalid_hash_never_authenticates():
    """The migration's locked accounts carry a hash bcrypt cannot match."""
    assert not verify_password("anything", "!")


def test_overlong_password_is_rejected_not_truncated():
    # bcrypt ignores bytes past 72, which would make two long passwords
    # interchangeable.
    with pytest.raises(ValueError):
        hash_password("x" * 73)


# --------------------------------------------------------------------------
# Registration and sign-in
# --------------------------------------------------------------------------


def test_register_returns_a_usable_token(client):
    email = _email()
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "test-password-123", "full_name": "New User"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["email"] == email
    assert body["stores"] == []

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == email


def test_register_never_returns_the_password_hash(client):
    response = client.post(
        "/auth/register",
        json={"email": _email(), "password": "test-password-123", "full_name": "New User"},
    )
    assert "password_hash" not in response.text
    assert "password" not in response.json()["user"]


def test_email_is_normalised_to_lowercase(client):
    email = _email().upper()
    client.post(
        "/auth/register",
        json={"email": email, "password": "test-password-123", "full_name": "Case Test"},
    )
    response = client.post(
        "/auth/login", json={"email": email.lower(), "password": "test-password-123"}
    )
    assert response.status_code == 200


def test_duplicate_email_is_a_conflict(client, owner):
    response = client.post(
        "/auth/register",
        json={"email": owner["email"], "password": "test-password-123", "full_name": "Copy"},
    )
    assert response.status_code == 409


def test_short_password_is_rejected(client):
    response = client.post(
        "/auth/register",
        json={"email": _email(), "password": "short", "full_name": "Short"},
    )
    assert response.status_code == 422


def test_login_with_wrong_password_fails(client, owner):
    response = client.post(
        "/auth/login", json={"email": owner["email"], "password": "not-the-password"}
    )
    assert response.status_code == 401


def test_unknown_email_and_wrong_password_are_indistinguishable(client, owner):
    """Otherwise the endpoint tells an attacker which addresses are registered."""
    unknown = client.post(
        "/auth/login", json={"email": _email(), "password": "test-password-123"}
    )
    wrong = client.post(
        "/auth/login", json={"email": owner["email"], "password": "not-the-password"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


# --------------------------------------------------------------------------
# Token handling
# --------------------------------------------------------------------------


def test_protected_route_requires_a_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/products").status_code == 401


def test_garbage_token_is_rejected(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_token_signed_with_another_secret_is_rejected(client, owner):
    import jwt

    forged = jwt.encode({"sub": str(owner["user"]["id"])}, "attacker-secret", algorithm="HS256")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_missing_bearer_prefix_is_rejected(client, owner):
    response = client.get("/auth/me", headers={"Authorization": owner["token"]})
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Profile and password management
# --------------------------------------------------------------------------


def test_profile_can_be_updated(client, new_user):
    account = new_user()
    response = client.patch(
        "/auth/me", headers=account["headers"], json={"full_name": "Renamed", "phone": "9998887777"}
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed"


def test_password_change_requires_the_current_password(client, new_user):
    account = new_user()
    response = client.post(
        "/auth/change-password",
        headers=account["headers"],
        json={"current_password": "wrong", "new_password": "a-new-password-1"},
    )
    assert response.status_code == 401


def test_password_change_invalidates_the_old_password(client, new_user):
    account = new_user()
    response = client.post(
        "/auth/change-password",
        headers=account["headers"],
        json={"current_password": account["password"], "new_password": "a-new-password-1"},
    )
    assert response.status_code == 200

    assert client.post(
        "/auth/login", json={"email": account["email"], "password": account["password"]}
    ).status_code == 401
    assert client.post(
        "/auth/login", json={"email": account["email"], "password": "a-new-password-1"}
    ).status_code == 200


def test_forgot_password_does_not_reveal_whether_the_account_exists(client, owner):
    known = client.post("/auth/forgot-password", json={"email": owner["email"]})
    unknown = client.post("/auth/forgot-password", json={"email": _email()})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
