"""Point-of-sale endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.deps import Store
from app.schemas.sale import CheckoutRequest, SaleDetail
from app.services import sales_service

router = APIRouter(prefix="/pos", tags=["pos"])


@router.post("/checkout", response_model=SaleDetail, status_code=status.HTTP_201_CREATED)
def checkout(payload: CheckoutRequest, context: Store) -> dict:
    """Complete a sale.

    Writes the invoice, its lines, its payments and one stock movement per line
    in a single transaction, then returns the receipt. Cashiers can do this —
    it is the one thing every role must be able to do.
    """
    return sales_service.checkout(
        context.store_id, payload.model_dump(mode="python"), context.user_id
    )
