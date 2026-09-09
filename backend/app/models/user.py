"""SQL access for users."""

from __future__ import annotations

from typing import Any

from app.database import query_one

COLUMNS = "id, email, full_name, phone, is_active, created_at, updated_at"


def get_by_id(user_id: int) -> dict[str, Any] | None:
    return query_one(f"SELECT {COLUMNS} FROM users WHERE id = %s", (user_id,))


def get_by_email(email: str) -> dict[str, Any] | None:
    """Public projection — never includes the hash."""
    return query_one(f"SELECT {COLUMNS} FROM users WHERE email = %s", (email,))


def get_credentials(email: str) -> dict[str, Any] | None:
    """Email lookup including the password hash, for sign-in only."""
    return query_one(
        "SELECT id, email, full_name, password_hash, is_active FROM users WHERE email = %s",
        (email,),
    )


def create(email: str, password_hash: str, full_name: str, phone: str | None) -> dict[str, Any]:
    return query_one(
        f"""
        INSERT INTO users (email, password_hash, full_name, phone)
        VALUES (%s, %s, %s, %s)
        RETURNING {COLUMNS}
        """,
        (email, password_hash, full_name, phone),
    )


def update_profile(user_id: int, full_name: str, phone: str | None) -> dict[str, Any] | None:
    return query_one(
        f"""
        UPDATE users SET full_name = %s, phone = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING {COLUMNS}
        """,
        (full_name, phone, user_id),
    )


def set_password(user_id: int, password_hash: str) -> int:
    from app.database import execute

    return execute(
        "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
        (password_hash, user_id),
    )
