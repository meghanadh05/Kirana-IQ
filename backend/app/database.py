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

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

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


def init_db() -> None:
    """Apply the schema. Idempotent."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
    logger.info("Database schema applied")


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
