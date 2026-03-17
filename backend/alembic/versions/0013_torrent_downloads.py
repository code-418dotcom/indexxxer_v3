"""Torrent download tracking table.

Revision ID: l3m5n7o9p1q3
Revises: k2l4m6n8o0p2
Create Date: 2026-03-17 00:00:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "l3m5n7o9p1q3"
down_revision = "k2l4m6n8o0p2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "torrent_downloads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("torrent_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column(
            "performer_id",
            sa.String(36),
            sa.ForeignKey("performers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("status_error", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("indexer", sa.String(255), nullable=True),
        sa.Column("destination_path", sa.Text(), nullable=True),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("torrent_downloads")
