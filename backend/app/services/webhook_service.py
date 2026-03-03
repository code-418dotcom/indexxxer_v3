"""
Webhook CRUD + delivery management.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import Webhook, WebhookDelivery
from app.schemas.webhook import WebhookCreate, WebhookDeliveryResponse, WebhookResponse, WebhookUpdate


async def create_webhook(
    db: AsyncSession, data: WebhookCreate, user_id: str | None = None
) -> WebhookResponse:
    wh = Webhook(
        user_id=user_id,
        name=data.name,
        url=data.url,
        events=data.events,
        secret=data.secret,
        enabled=data.enabled,
    )
    db.add(wh)
    await db.flush()
    await db.refresh(wh)
    return WebhookResponse.model_validate(wh)


async def list_webhooks(db: AsyncSession) -> list[WebhookResponse]:
    result = await db.execute(select(Webhook).order_by(Webhook.created_at))
    return [WebhookResponse.model_validate(wh) for wh in result.scalars()]


async def get_webhook(db: AsyncSession, webhook_id: str) -> Webhook:
    wh = await db.get(Webhook, webhook_id)
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return wh


async def update_webhook(
    db: AsyncSession, webhook_id: str, data: WebhookUpdate
) -> WebhookResponse:
    wh = await get_webhook(db, webhook_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(wh, field, value)
    await db.flush()
    await db.refresh(wh)
    return WebhookResponse.model_validate(wh)


async def delete_webhook(db: AsyncSession, webhook_id: str) -> None:
    wh = await get_webhook(db, webhook_id)
    await db.delete(wh)
    await db.flush()


async def list_deliveries(
    db: AsyncSession, webhook_id: str, limit: int = 50
) -> list[WebhookDeliveryResponse]:
    result = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    return [WebhookDeliveryResponse.model_validate(d) for d in result.scalars()]


async def record_delivery(
    db: AsyncSession, webhook_id: str, event_type: str, payload: dict
) -> WebhookDelivery:
    delivery = WebhookDelivery(
        webhook_id=webhook_id,
        event_type=event_type,
        payload=payload,
        status="pending",
    )
    db.add(delivery)
    await db.flush()
    await db.refresh(delivery)
    return delivery


async def update_delivery_result(
    db: AsyncSession,
    delivery_id: str,
    status: str,
    http_status: int | None = None,
    error: str | None = None,
) -> None:
    from datetime import datetime, timezone

    delivery = await db.get(WebhookDelivery, delivery_id)
    if not delivery:
        return
    delivery.status = status
    if http_status is not None:
        delivery.http_status = http_status
    if error is not None:
        delivery.error = error
    if status == "delivered":
        delivery.delivered_at = datetime.now(timezone.utc)
    await db.flush()
