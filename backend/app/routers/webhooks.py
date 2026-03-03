"""
Webhook management endpoints (admin only).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.webhook import (
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookUpdate,
)
from app.services import webhook_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_admin = Depends(require_admin)


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(_: User = _admin, db: AsyncSession = Depends(get_db)):
    return await webhook_service.list_webhooks(db)


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    current_user: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    return await webhook_service.create_webhook(db, body, user_id=current_user.id)


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str, _: User = _admin, db: AsyncSession = Depends(get_db)
):
    wh = await webhook_service.get_webhook(db, webhook_id)
    return WebhookResponse.model_validate(wh)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    body: WebhookUpdate,
    _: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    return await webhook_service.update_webhook(db, webhook_id, body)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str, _: User = _admin, db: AsyncSession = Depends(get_db)
):
    await webhook_service.delete_webhook(db, webhook_id)


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_deliveries(
    webhook_id: str, _: User = _admin, db: AsyncSession = Depends(get_db)
):
    return await webhook_service.list_deliveries(db, webhook_id, limit=50)


@router.post("/{webhook_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_webhook(
    webhook_id: str,
    current_user: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    """Fire a test 'ping' event to the webhook."""
    delivery = await webhook_service.record_delivery(
        db, webhook_id, "ping", {"message": "test"}
    )
    from app.workers.tasks.webhook import deliver_webhook_task

    deliver_webhook_task.apply_async(
        kwargs={
            "delivery_id": delivery.id,
            "webhook_id": webhook_id,
            "event_type": "ping",
            "payload": {"message": "test"},
        },
        queue="webhooks",
    )
    return {"delivery_id": delivery.id}
