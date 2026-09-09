"""Sales history endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.deps import ManagerStore, Store
from app.errors import ValidationError
from app.schemas.sale import (
    CancelRequest,
    PaymentMethod,
    SaleDetail,
    SalePage,
    SaleStatus,
)
from app.services import sales_service

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("", response_model=SalePage)
def list_sales(
    context: Store,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    payment_method: PaymentMethod | None = Query(default=None),
    status: SaleStatus | None = Query(default=None),
    customer_id: int | None = Query(default=None, gt=0),
    search: str | None = Query(default=None, description="Invoice number, customer name or phone"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Invoices, newest first, with the filters the sales screen offers."""
    if start_date and end_date and start_date > end_date:
        raise ValidationError("start_date must not be after end_date")

    return sales_service.list_sales(
        context.store_id,
        {
            "start_date": start_date,
            "end_date": end_date,
            "payment_method": payment_method,
            "status": status,
            "customer_id": customer_id,
            "search": search,
        },
        limit=limit,
        offset=offset,
    )


@router.get("/{sale_id}", response_model=SaleDetail)
def get_sale(sale_id: int, context: Store) -> dict:
    """One invoice with its lines and payments — also the receipt payload."""
    return sales_service.get_sale(context.store_id, sale_id)


@router.post("/{sale_id}/cancel", response_model=SaleDetail)
def cancel_sale(sale_id: int, payload: CancelRequest, context: ManagerStore) -> dict:
    """Void a sale and return its stock. Managers and owners only."""
    return sales_service.cancel_sale(
        context.store_id, sale_id, context.user_id, payload.reason
    )
