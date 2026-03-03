"""
Celery task for delivering webhook payloads with HMAC-SHA256 signatures.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx
import structlog

from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)

# Retry countdown in seconds: [immediate, 60s, 300s]
_RETRY_COUNTDOWNS = [0, 60, 300]


@celery_app.task(
    bind=True,
    queue="webhooks",
    max_retries=2,
    name="app.workers.tasks.webhook.deliver_webhook_task",
)
def deliver_webhook_task(
    self,
    delivery_id: str,
    webhook_id: str,
    event_type: str,
    payload: dict,
) -> None:
    asyncio.run(_deliver(self, delivery_id, webhook_id, event_type, payload))


async def _deliver(task, delivery_id: str, webhook_id: str, event_type: str, payload: dict):
    from app.models.webhook import Webhook, WebhookDelivery

    async with task_session() as session:
        wh = await session.get(Webhook, webhook_id)
        delivery = await session.get(WebhookDelivery, delivery_id)
        if not wh or not delivery:
            log.error("webhook.not_found", webhook_id=webhook_id, delivery_id=delivery_id)
            return

        body_data = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }
        body_bytes = json.dumps(body_data, separators=(",", ":")).encode()

        headers = {"Content-Type": "application/json"}
        if wh.secret:
            sig = hmac.new(wh.secret.encode(), body_bytes, hashlib.sha256).hexdigest()
            headers["X-Indexxxer-Signature"] = f"sha256={sig}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(wh.url, content=body_bytes, headers=headers)

            delivery.http_status = resp.status_code
            delivery.attempts += 1

            if resp.is_success:
                delivery.status = "delivered"
                delivery.delivered_at = datetime.now(timezone.utc)
                log.info(
                    "webhook.delivered",
                    webhook_id=webhook_id,
                    delivery_id=delivery_id,
                    http_status=resp.status_code,
                )
            else:
                _handle_failure(task, delivery, f"HTTP {resp.status_code}")
        except Exception as exc:
            delivery.attempts += 1
            _handle_failure(task, delivery, str(exc))

        await session.flush()


def _handle_failure(task, delivery, error: str) -> None:
    attempts = delivery.attempts
    delivery.error = error

    if attempts <= task.max_retries:
        countdown = _RETRY_COUNTDOWNS[min(attempts, len(_RETRY_COUNTDOWNS) - 1)]
        delivery.status = "pending"
        log.warning(
            "webhook.retry",
            delivery_id=delivery.id,
            attempts=attempts,
            countdown=countdown,
            error=error,
        )
        task.retry(
            kwargs={
                "delivery_id": delivery.id,
                "webhook_id": delivery.webhook_id,
                "event_type": delivery.event_type,
                "payload": delivery.payload or {},
            },
            countdown=countdown,
        )
    else:
        delivery.status = "failed"
        log.error("webhook.failed", delivery_id=delivery.id, error=error)
