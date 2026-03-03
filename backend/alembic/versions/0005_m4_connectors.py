"""M4 Connectors — source_credentials table

Revision ID: d5f7a9c1e3g4
Revises: c4e6f8b0d2f3
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5f7a9c1e3g4"
down_revision: Union[str, None] = "c4e6f8b0d2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS source_credentials (
            id           VARCHAR(36) PRIMARY KEY,
            source_id    VARCHAR(36) UNIQUE NOT NULL REFERENCES media_sources(id) ON DELETE CASCADE,
            host         VARCHAR(255) NOT NULL,
            port         INTEGER,
            username     VARCHAR(255),
            password_enc TEXT,
            domain       VARCHAR(255),
            share        VARCHAR(255),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_creds_source ON source_credentials(source_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_source_creds_source")
    op.execute("DROP TABLE IF EXISTS source_credentials")
