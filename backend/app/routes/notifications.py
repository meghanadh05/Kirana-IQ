"""Notification centre endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.deps import Store
from app.errors import NotFoundError
from app.models import notification as notification_model
from app.schemas.business import NotificationList, NotificationOut, ReadUpdate
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
def list_notifications(
    context: Store,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    return {
        "items": notification_model.list_notifications(context.store_id, unread_only, limit),
        "unread": notification_model.unread_count(context.store_id),
    }


@router.post("/refresh")
def refresh(context: Store) -> dict:
    """Regenerate alerts from current stock, forecasts and open orders."""
    return notification_service.refresh(context.store_id)


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, payload: ReadUpdate, context: Store) -> dict:
    updated = notification_model.mark_read(notification_id, context.store_id, payload.is_read)
    if updated is None:
        raise NotFoundError(f"Notification {notification_id} not found")
    return updated


@router.post("/read-all")
def mark_all_read(context: Store) -> dict:
    return {"updated": notification_model.mark_all_read(context.store_id)}


@router.delete("/{notification_id}")
def delete_notification(notification_id: int, context: Store) -> dict:
    if not notification_model.delete(notification_id, context.store_id):
        raise NotFoundError(f"Notification {notification_id} not found")
    return {"status": "deleted"}
