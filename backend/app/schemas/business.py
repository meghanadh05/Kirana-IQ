"""Request/response models for customers, expenses, notifications and reports."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

ExpenseCategory = Literal[
    "Rent", "Electricity", "Salaries", "Transport", "Maintenance", "Other"
]
NotificationType = Literal["CRITICAL", "PURCHASE", "ANOMALY", "SYSTEM", "STOCK"]
Period = Literal["today", "7d", "30d", "90d", "365d"]


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=1000)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=1000)


class CustomerOut(BaseModel):
    id: int
    store_id: int
    name: str
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    created_at: datetime
    total_spent: Decimal = Decimal("0")
    purchase_count: int = 0
    last_purchase: date | None = None


class CustomerDetail(CustomerOut):
    average_order_value: float = 0
    purchases: list[dict] = []


class CustomerPage(BaseModel):
    items: list[CustomerOut]
    total: int
    limit: int
    offset: int


class ExpenseCreate(BaseModel):
    category: ExpenseCategory
    description: str | None = Field(default=None, max_length=300)
    amount: Decimal = Field(gt=0, le=100_000_000, decimal_places=2)
    expense_date: date
    payment_method: str = Field(default="CASH", max_length=20)
    notes: str | None = Field(default=None, max_length=1000)


class ExpenseUpdate(BaseModel):
    category: ExpenseCategory | None = None
    description: str | None = Field(default=None, max_length=300)
    amount: Decimal | None = Field(default=None, gt=0, le=100_000_000, decimal_places=2)
    expense_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)


class ExpenseOut(BaseModel):
    id: int
    store_id: int
    category: str
    description: str | None = None
    amount: Decimal
    expense_date: date
    payment_method: str
    notes: str | None = None
    created_at: datetime


class ExpensePage(BaseModel):
    items: list[ExpenseOut]
    total: int
    total_amount: float
    by_category: list[dict]
    limit: int
    offset: int


class NotificationOut(BaseModel):
    id: int
    store_id: int
    type: NotificationType
    severity: str
    title: str
    message: str
    link: str | None = None
    is_read: bool
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread: int


class ReadUpdate(BaseModel):
    is_read: bool = True
