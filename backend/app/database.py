"""Thin PostgreSQL access layer built on psycopg 3.

Deliberately not an ORM: a single connection pool plus small helpers that
return plain dictionaries. Everything else in the app speaks SQL directly.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Return the process-wide connection pool, creating it on first use."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        _pool.open()
    return _pool


def close_pool() -> None:
    """Close the pool on application shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Borrow a connection from the pool; commits on success, rolls back on error."""
    with get_pool().connection() as conn:
        yield conn


def query_all(sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: tuple | dict | None = None) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: tuple | dict | None = None) -> int:
    """Run a statement and return the number of affected rows."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


@contextmanager
def transaction() -> Iterator[Connection]:
    """A connection whose work commits as one unit, or not at all.

    psycopg wraps the `with conn` block in a transaction already; this exists so
    call sites read as what they are — `with transaction() as conn:` around a
    checkout says "these six statements land together or none of them do".
    """
    with get_pool().connection() as conn:
        yield conn


def applied_migrations(conn: Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute("SELECT version FROM schema_migrations")
        return {row["version"] for row in cur.fetchall()}


def init_db() -> None:
    """Apply any migrations this database has not seen yet.

    Migrations are plain `.sql` files applied in filename order and recorded in
    `schema_migrations`, each inside its own transaction. Ad-hoc schema
    recreation would lose a live store's data; this will not.
    """
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        logger.warning("No migrations found in %s", MIGRATIONS_DIR)
        return

    with get_connection() as conn:
        done = applied_migrations(conn)

    for path in files:
        version = path.stem
        if version in done:
            continue
        logger.info("Applying migration %s", version)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(path.read_text(encoding="utf-8"))
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
            )
        logger.info("Migration %s applied", version)


def check_connection() -> bool:
    """Return True when the database answers a trivial query."""
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as exc:  # noqa: BLE001 - health check must never raise
        logger.warning("Database health check failed: %s", exc)
        return False
