"""M4 Analytics — query_logs table

Revision ID: f7a9c1e3g5i6
Revises: e6f8b0d2f4h5
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a9c1e3g5i6"
down_revision: Union[str, None] = "e6f8b0d2f4h5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS query_logs (
            id           VARCHAR(36) PRIMARY KEY,
            query        TEXT,
            search_mode  VARCHAR(20),
            result_count INTEGER,
            latency_ms   INTEGER,
            user_id      VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_qlog_created ON query_logs(created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_qlog_created")
    op.execute("DROP TABLE IF EXISTS query_logs")
