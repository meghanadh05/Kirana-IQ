"""Request/response models for the POS and sales history."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PaymentMethod = Literal["CASH", "UPI", "CARD", "MIXED", "OTHER"]
TenderMethod = Literal["CASH", "UPI", "CARD", "OTHER"]
SaleStatus = Literal["COMPLETED", "CANCELLED", "RETURNED"]


class CartLine(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100_000)
    # Optional overrides. Omit them and the server prices the line from the
    # catalogue, which is what the POS does.
    unit_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    discount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)


class PaymentSplit(BaseModel):
    method: TenderMethod
    amount: Decimal = Field(ge=0, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)


class CheckoutRequest(BaseModel):
    items: list[CartLine] = Field(min_length=1, max_length=200)
    payment_method: PaymentMethod = "CASH"
    payments: list[PaymentSplit] | None = None
    discount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    amount_received: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    customer_id: int | None = Field(default=None, gt=0)
    customer_name: str | None = Field(default=None, max_length=120)
    customer_phone: str | None = Field(default=None, max_length=20)
    payment_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)
    sale_date: date | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [{"product_id": 1, "quantity": 2}],
                "payment_method": "CASH",
                "amount_received": "100.00",
                "customer_phone": "9876543210",
            }
        }
    )


class SaleItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    sku: str
    quantity: int
    unit_price: Decimal
    cost_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    line_total: Decimal


class PaymentOut(BaseModel):
    id: int
    method: str
    amount: Decimal
    reference: str | None = None


class SaleOut(BaseModel):
    """A sale in a list. Line items are only loaded for the detail view."""

    id: int
    store_id: int
    invoice_number: str
    customer_id: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    cost_total: Decimal
    payment_method: str
    amount_received: Decimal
    change_due: Decimal
    status: SaleStatus
    notes: str | None = None
    sale_date: date
    created_at: datetime
    created_by: int | None = None
    created_by_name: str | None = None
    item_count: int = 0
    unit_count: int = 0


class SaleDetail(SaleOut):
    items: list[SaleItemOut]
    payments: list[PaymentOut]
    gross_profit: float


class SalePage(BaseModel):
    items: list[SaleOut]
    total: int
    limit: int
    offset: int


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)
