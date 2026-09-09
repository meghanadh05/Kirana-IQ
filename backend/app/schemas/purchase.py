"""Request/response models for suppliers and purchase orders."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

PurchaseStatus = Literal["DRAFT", "ORDERED", "PARTIALLY_RECEIVED", "RECEIVED", "CANCELLED"]


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=300)
    gst_number: str | None = Field(default=None, max_length=20)
    default_lead_time_days: int = Field(default=3, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=1000)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=300)
    gst_number: str | None = Field(default=None, max_length=20)
    default_lead_time_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class SupplierOut(BaseModel):
    id: int
    store_id: int
    name: str
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    gst_number: str | None = None
    default_lead_time_days: int
    notes: str | None = None
    is_active: bool
    created_at: datetime
    product_count: int = 0
    open_orders: int = 0
    total_purchased: float = 0


class SupplierDetail(SupplierOut):
    products: list[dict]
    purchase_orders: list[dict]
    order_count: int = 0


class PurchaseLine(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1_000_000)
    cost_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int | None = Field(default=None, gt=0)
    items: list[PurchaseLine] = Field(min_length=1, max_length=500)
    status: Literal["DRAFT", "ORDERED"] = "DRAFT"
    expected_delivery: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class PurchaseItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    sku: str
    unit: str
    quantity: int
    received_quantity: int
    cost_price: Decimal
    tax_rate: Decimal
    line_total: Decimal
    current_stock: int


class PurchaseOrderOut(BaseModel):
    id: int
    store_id: int
    po_number: str
    supplier_id: int | None = None
    supplier_name: str | None = None
    status: PurchaseStatus
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    expected_delivery: date | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    received_at: datetime | None = None
    item_count: int = 0
    unit_count: int = 0
    received_count: int = 0


class PurchaseOrderDetail(PurchaseOrderOut):
    supplier_phone: str | None = None
    supplier_contact: str | None = None
    items: list[PurchaseItemOut]


class PurchaseOrderPage(BaseModel):
    items: list[PurchaseOrderOut]
    total: int
    limit: int
    offset: int


class StatusUpdate(BaseModel):
    status: PurchaseStatus


class ReceiptLine(BaseModel):
    item_id: int = Field(gt=0)
    quantity: int = Field(ge=0, le=1_000_000)


class ReceiveRequest(BaseModel):
    """Omit `items` to receive everything still outstanding."""

    items: list[ReceiptLine] | None = None


class ReorderGroup(BaseModel):
    supplier_id: int | None = None
    supplier_name: str | None = None
    expected_delivery: str
    product_count: int
    total_units: int
    estimated_cost: float
    items: list[dict]


class ReorderSuggestions(BaseModel):
    groups: list[ReorderGroup]
    total_products: int


class ReorderToPurchase(BaseModel):
    supplier_id: int | None = Field(default=None, gt=0)
    product_ids: list[int] | None = Field(default=None, max_length=500)
