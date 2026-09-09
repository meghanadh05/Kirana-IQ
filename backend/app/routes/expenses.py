"""Expense endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, status

from app.deps import ManagerStore, Store
from app.errors import NotFoundError, ValidationError
from app.models import expense as expense_model
from app.schemas.business import (
    ExpenseCategory,
    ExpenseCreate,
    ExpenseOut,
    ExpensePage,
    ExpenseUpdate,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=ExpensePage)
def list_expenses(
    context: Store,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    category: ExpenseCategory | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise ValidationError("start_date must not be after end_date")

    return {
        "items": expense_model.list_expenses(
            context.store_id, start_date, end_date, category, limit, offset
        ),
        "total": expense_model.count_expenses(context.store_id, start_date, end_date, category),
        "total_amount": round(
            expense_model.total_amount(context.store_id, start_date, end_date), 2
        ),
        "by_category": [
            {
                "category": row["category"],
                "total": round(float(row["total"]), 2),
                "entries": int(row["entries"]),
            }
            for row in expense_model.totals_by_category(context.store_id, start_date, end_date)
        ],
        "limit": limit,
        "offset": offset,
    }


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, context: ManagerStore) -> dict:
    return expense_model.create(context.store_id, payload.model_dump(), context.user_id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, payload: ExpenseUpdate, context: ManagerStore) -> dict:
    if expense_model.get(expense_id, context.store_id) is None:
        raise NotFoundError(f"Expense {expense_id} not found")
    return expense_model.update(
        expense_id, context.store_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{expense_id}")
def delete_expense(expense_id: int, context: ManagerStore) -> dict:
    if expense_model.get(expense_id, context.store_id) is None:
        raise NotFoundError(f"Expense {expense_id} not found")
    expense_model.delete(expense_id, context.store_id)
    return {"status": "deleted"}
