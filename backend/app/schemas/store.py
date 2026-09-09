"""Request/response models for stores, settings and team members."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

BusinessType = Literal[
    "KIRANA", "GROCERY", "MINI_SUPERMARKET", "PHARMACY", "CONVENIENCE_STORE", "OTHER"
]
Role = Literal["OWNER", "MANAGER", "CASHIER"]


class StoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    owner_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    pin_code: str | None = Field(default=None, max_length=12)
    gst_number: str | None = Field(default=None, max_length=20)
    currency: str = Field(default="INR", max_length=8)
    business_type: BusinessType = "KIRANA"


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    owner_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    pin_code: str | None = Field(default=None, max_length=12)
    gst_number: str | None = Field(default=None, max_length=20)
    currency: str | None = Field(default=None, max_length=8)
    business_type: BusinessType | None = None


class StoreOut(BaseModel):
    id: int
    name: str
    owner_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pin_code: str | None = None
    gst_number: str | None = None
    currency: str
    business_type: str
    is_demo: bool
    onboarding_step: int
    onboarding_completed: bool
    created_at: datetime
    role: str | None = None


class OnboardingStep(BaseModel):
    step: int = Field(ge=1, le=4)


class StoreSettingsOut(BaseModel):
    store_id: int
    low_stock_threshold: int
    default_tax_rate: Decimal
    default_lead_time_days: int
    invoice_prefix: str
    purchase_order_prefix: str
    financial_year_start_month: int
    timezone: str
    critical_cover_days: Decimal
    medium_cover_buffer_days: Decimal
    overstock_cover_days: Decimal
    safety_days: int
    service_level_z: Decimal


class StoreSettingsUpdate(BaseModel):
    low_stock_threshold: int | None = Field(default=None, ge=0, le=100_000)
    default_tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    default_lead_time_days: int | None = Field(default=None, ge=0, le=365)
    invoice_prefix: str | None = Field(default=None, min_length=1, max_length=12)
    purchase_order_prefix: str | None = Field(default=None, min_length=1, max_length=12)
    financial_year_start_month: int | None = Field(default=None, ge=1, le=12)
    timezone: str | None = Field(default=None, max_length=64)
    critical_cover_days: Decimal | None = Field(default=None, ge=0, le=365)
    medium_cover_buffer_days: Decimal | None = Field(default=None, ge=0, le=365)
    overstock_cover_days: Decimal | None = Field(default=None, ge=0, le=3650)
    safety_days: int | None = Field(default=None, ge=0, le=365)
    service_level_z: Decimal | None = Field(default=None, ge=0, le=5)


class MemberOut(BaseModel):
    id: int
    store_id: int
    user_id: int
    role: Role
    email: str
    full_name: str
    phone: str | None = None
    created_at: datetime


class MemberCreate(BaseModel):
    email: EmailStr
    role: Role = "CASHIER"


class MemberRoleUpdate(BaseModel):
    role: Role
