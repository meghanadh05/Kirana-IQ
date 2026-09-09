"""Kirana-IQ FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import check_connection, close_pool, init_db
from app.errors import DomainError
from app.routes import (
    analytics,
    auth,
    categories,
    customers,
    dashboard,
    expenses,
    forecast,
    inventory,
    notifications,
    pos,
    products,
    purchases,
    reports,
    sales,
    search,
    stores,
    suppliers,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Apply migrations on startup; keep serving even if the DB is not up yet."""
    if not settings.is_development and settings.jwt_secret_is_default:
        raise RuntimeError(
            "JWT_SECRET is still the development default. Set it before deploying."
        )

    try:
        init_db()
    except Exception as exc:  # noqa: BLE001 - surfaced through /health instead
        logger.warning("Could not initialise database at startup: %s", exc)
    yield
    close_pool()


app = FastAPI(
    title=settings.app_name,
    description="Intelligent POS, inventory and demand forecasting for small retail stores.",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # An explicit allowlist, never "*": credentialed requests from any origin
    # would make every signed-in browser a confused deputy.
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Business failures carry their own status code and a safe message."""
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=headers
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the trace, return none of it.

    A stack trace in a client response leaks table names, file paths and library
    versions. The server log is where it belongs.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. The error has been logged."},
    )


app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(pos.router)
app.include_router(sales.router)
app.include_router(forecast.router)
app.include_router(inventory.router)
app.include_router(suppliers.router)
app.include_router(purchases.router)
app.include_router(customers.router)
app.include_router(expenses.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(search.router)
app.include_router(dashboard.router)
# Demand-intelligence analytics (forecast risk, anomalies, movers) and business
# analytics (revenue, profit, categories) share the /analytics prefix.
app.include_router(analytics.router)
app.include_router(dashboard.analytics)


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
