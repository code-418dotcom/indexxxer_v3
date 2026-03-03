"""M4 Webhooks — webhooks + webhook_deliveries tables

Revision ID: e6f8b0d2f4h5
Revises: d5f7a9c1e3g4
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f8b0d2f4h5"
down_revision: Union[str, None] = "d5f7a9c1e3g4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhooks (
            id         VARCHAR(36) PRIMARY KEY,
            user_id    VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
            name       VARCHAR(255) NOT NULL,
            url        VARCHAR(2048) NOT NULL,
            events     JSONB NOT NULL DEFAULT '[]',
            secret     VARCHAR(255),
            enabled    BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id           VARCHAR(36) PRIMARY KEY,
            webhook_id   VARCHAR(36) NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
            event_type   VARCHAR(100),
            payload      JSONB,
            status       VARCHAR(20) NOT NULL DEFAULT 'pending',
            http_status  INTEGER,
            error        TEXT,
            attempts     INTEGER NOT NULL DEFAULT 0,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            delivered_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_deliveries_webhook ON webhook_deliveries(webhook_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_deliveries_webhook")
    op.execute("DROP TABLE IF EXISTS webhook_deliveries")
    op.execute("DROP INDEX IF EXISTS idx_webhooks_user")
    op.execute("DROP TABLE IF EXISTS webhooks")
