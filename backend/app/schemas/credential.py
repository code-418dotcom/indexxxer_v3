from datetime import datetime

from pydantic import BaseModel


class CredentialCreate(BaseModel):
    host: str
    port: int | None = None
    username: str | None = None
    password: str | None = None  # Plaintext; stored encrypted
    domain: str | None = None
    share: str | None = None


class CredentialUpdate(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    domain: str | None = None
    share: str | None = None


class CredentialResponse(BaseModel):
    id: str
    source_id: str
    host: str
    port: int | None = None
    username: str | None = None
    domain: str | None = None
    share: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
