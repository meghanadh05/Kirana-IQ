"""Report endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Response

from app.deps import Store
from app.schemas.business import Period
from app.services import business_service, report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def list_reports(context: Store) -> list[dict]:
    """The reports available for download."""
    return report_service.catalogue()


@router.get("/{report}", response_class=Response)
def download_report(
    report: str,
    context: Store,
    period: Period = Query(default="30d"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> Response:
    """Download one report as CSV."""
    start, end = business_service.resolve_period(period, start_date, end_date)
    content = report_service.build(report, context.store_id, start, end)

    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{report}-{start}-to-{end}.csv"'
        },
    )
