from datetime import datetime

from pydantic import BaseModel


class WebhookCreate(BaseModel):
    name: str
    url: str
    events: list[str] = []
    secret: str | None = None
    enabled: bool = True


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    secret: str | None = None
    enabled: bool | None = None


class WebhookResponse(BaseModel):
    id: str
    user_id: str | None = None
    name: str
    url: str
    events: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryResponse(BaseModel):
    id: str
    webhook_id: str
    event_type: str | None = None
    status: str
    http_status: int | None = None
    error: str | None = None
    attempts: int
    created_at: datetime
    delivered_at: datetime | None = None

    model_config = {"from_attributes": True}
