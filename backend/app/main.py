"""Kirana-IQ FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import check_connection, close_pool, init_db
from app.routes import products, sales

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Apply the schema on startup; keep serving even if the DB is not up yet."""
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001 - surfaced through /health instead
        logger.warning("Could not initialise database at startup: %s", exc)
    yield
    close_pool()


app = FastAPI(
    title=settings.app_name,
    description="AI-powered inventory forecasting for small retail stores.",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(products.router)
app.include_router(sales.router)


@app.get("/health", tags=["system"])
def health() -> dict:
    """Liveness/readiness probe. Reports whether PostgreSQL is reachable."""
    database_ok = check_connection()
    return {
        "status": "ok" if database_ok else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "database": "connected" if database_ok else "unavailable",
    }


@app.get("/", tags=["system"])
def root() -> dict:
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}
