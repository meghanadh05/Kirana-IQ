"""SQL access for the in-app notification centre."""

from __future__ import annotations

from typing import Any

from app.database import execute, query_all, query_one

COLUMNS = """
    id, store_id, type, severity, title, message, link, dedupe_key, is_read, created_at
"""


def list_notifications(
    store_id: int, unread_only: bool = False, limit: int = 50
) -> list[dict[str, Any]]:
    clauses = ["store_id = %s"]
    params: list[Any] = [store_id]
    if unread_only:
        clauses.append("is_read = FALSE")

    params.append(limit)
    return query_all(
        f"SELECT {COLUMNS} FROM notifications WHERE {' AND '.join(clauses)} "
        f"ORDER BY is_read, created_at DESC LIMIT %s",
        tuple(params),
    )


def unread_count(store_id: int) -> int:
    row = query_one(
        "SELECT COUNT(*) AS total FROM notifications WHERE store_id = %s AND is_read = FALSE",
        (store_id,),
    )
    return int(row["total"]) if row else 0


def create(
    store_id: int,
    notification_type: str,
    severity: str,
    title: str,
    message: str,
    link: str | None = None,
    dedupe_key: str | None = None,
) -> dict[str, Any] | None:
    """Insert a notification, refreshing an existing one with the same dedupe key.

    Alerts are regenerated on a schedule, so "Dove Soap is running out" must
    update in place rather than appear ten times.
    """
    return query_one(
        f"""
        INSERT INTO notifications (store_id, type, severity, title, message, link, dedupe_key)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (store_id, dedupe_key) WHERE dedupe_key IS NOT NULL
        DO UPDATE SET message = EXCLUDED.message, severity = EXCLUDED.severity,
                      title = EXCLUDED.title, created_at = NOW()
        RETURNING {COLUMNS}
        """,
        (store_id, notification_type, severity, title, message, link, dedupe_key),
    )


def mark_read(notification_id: int, store_id: int, is_read: bool = True) -> dict[str, Any] | None:
    return query_one(
        f"UPDATE notifications SET is_read = %s WHERE id = %s AND store_id = %s "
        f"RETURNING {COLUMNS}",
        (is_read, notification_id, store_id),
    )


def mark_all_read(store_id: int) -> int:
    return execute(
        "UPDATE notifications SET is_read = TRUE WHERE store_id = %s AND is_read = FALSE",
        (store_id,),
    )


def delete(notification_id: int, store_id: int) -> int:
    return execute(
        "DELETE FROM notifications WHERE id = %s AND store_id = %s", (notification_id, store_id)
    )
