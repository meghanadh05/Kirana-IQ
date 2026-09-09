"""Registration, sign-in and password management.

Sign-up creates a user only. The store is created separately by the onboarding
wizard, because a user may own more than one and may be invited to someone
else's before ever creating their own.
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg.errors import UniqueViolation

from app.errors import AuthenticationError, ConflictError, NotFoundError
from app.models import store as store_model
from app.models import user as user_model
from app.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)


def normalise_email(email: str) -> str:
    return email.strip().lower()


def register(email: str, password: str, full_name: str, phone: str | None = None) -> dict[str, Any]:
    """Create an account and return it with a signed session token."""
    email = normalise_email(email)
    try:
        user = user_model.create(email, hash_password(password), full_name.strip(), phone)
    except UniqueViolation as exc:
        raise ConflictError("An account with this email already exists") from exc

    return _session(user)


def login(email: str, password: str) -> dict[str, Any]:
    """Verify credentials and issue a token.

    The same message is returned for an unknown email and a wrong password, so
    the endpoint cannot be used to enumerate registered accounts.
    """
    record = user_model.get_credentials(normalise_email(email))
    if record is None or not verify_password(password, record["password_hash"]):
        raise AuthenticationError("Incorrect email or password")
    if not record["is_active"]:
        raise AuthenticationError("This account has been deactivated")

    user = user_model.get_by_id(record["id"])
    return _session(user)


def change_password(user_id: int, current_password: str, new_password: str) -> None:
    record = user_model.get_credentials(user_model.get_by_id(user_id)["email"])
    if record is None:
        raise NotFoundError("User not found")
    if not verify_password(current_password, record["password_hash"]):
        raise AuthenticationError("Current password is incorrect")
    user_model.set_password(user_id, hash_password(new_password))


def request_password_reset(email: str) -> None:
    """Start a password reset.

    Delivery is not wired up — there is no mail provider in this deployment — so
    this records the request and returns. The endpoint deliberately behaves
    identically for known and unknown addresses so it cannot confirm whether an
    account exists.
    """
    user = user_model.get_by_email(normalise_email(email))
    if user is not None:
        logger.info("Password reset requested for user %s", user["id"])


def _session(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "access_token": create_access_token(user["id"], user["email"]),
        "token_type": "bearer",
        "user": user,
        "stores": store_model.list_for_user(user["id"]),
    }
