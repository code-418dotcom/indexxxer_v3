"""Add perceptual_hash and duplicate_group columns to media_items.

Revision ID: j1k3l5m7n9o1
Revises: i0j2c4e6f8h9
Create Date: 2026-03-15 00:00:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "j1k3l5m7n9o1"
down_revision = "i0j2c4e6f8h9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_items",
        sa.Column("perceptual_hash", sa.String(16), nullable=True),
    )
    op.add_column(
        "media_items",
        sa.Column("duplicate_group", sa.String(36), nullable=True),
    )
    op.create_index("idx_media_phash", "media_items", ["perceptual_hash"])
    op.create_index("idx_media_dupgroup", "media_items", ["duplicate_group"])


def downgrade() -> None:
    op.drop_index("idx_media_dupgroup", table_name="media_items")
    op.drop_index("idx_media_phash", table_name="media_items")
    op.drop_column("media_items", "duplicate_group")
    op.drop_column("media_items", "perceptual_hash")
