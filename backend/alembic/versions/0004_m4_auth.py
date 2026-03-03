"""M4 Auth — users table + saved_filters.user_id FK

Revision ID: c4e6f8b0d2f3
Revises: b3d5f7a9c1e2
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e6f8b0d2f3"
down_revision: Union[str, None] = "b3d5f7a9c1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            VARCHAR(36) PRIMARY KEY,
            email         VARCHAR(255) UNIQUE NOT NULL,
            username      VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255),
            role          VARCHAR(20)  NOT NULL DEFAULT 'user',
            enabled       BOOLEAN      NOT NULL DEFAULT true,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON users(email)")

    # Add nullable user_id FK to saved_filters for future per-user filters
    op.add_column(
        "saved_filters",
        sa.Column("user_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_saved_filters_user_id",
        "saved_filters",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_saved_filters_user_id", "saved_filters", type_="foreignkey")
    op.drop_column("saved_filters", "user_id")
    op.execute("DROP INDEX IF EXISTS idx_user_email")
    op.execute("DROP TABLE IF EXISTS users")
