"""Two-phase dedup: frame hashes for videos, gallery dedup.

Revision ID: k2l4m6n8o0p2
Revises: j1k3l5m7n9o1
Create Date: 2026-03-17 00:00:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "k2l4m6n8o0p2"
down_revision = "j1k3l5m7n9o1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── media_frame_hashes table ────────────────────────────────────────────
    op.create_table(
        "media_frame_hashes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "media_item_id",
            sa.String(36),
            sa.ForeignKey("media_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("frame_position", sa.String(10), nullable=False),
        sa.Column("phash", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_mfh_media", "media_frame_hashes", ["media_item_id"])
    op.create_index("idx_mfh_phash", "media_frame_hashes", ["phash"])

    # ── media_items: add dedup_status ───────────────────────────────────────
    op.add_column(
        "media_items",
        sa.Column("dedup_status", sa.String(20), nullable=False, server_default="pending"),
    )

    # ── galleries: add dedup columns ───────────────────────────────────────
    op.add_column("galleries", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column("galleries", sa.Column("duplicate_group", sa.String(36), nullable=True))
    op.add_column(
        "galleries",
        sa.Column("dedup_status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.create_index("idx_gallery_content_hash", "galleries", ["content_hash"])
    op.create_index("idx_gallery_dupgroup", "galleries", ["duplicate_group"])

    # ── gallery_images: add phash ──────────────────────────────────────────
    op.add_column("gallery_images", sa.Column("phash", sa.String(16), nullable=True))
    op.create_index("idx_gi_phash", "gallery_images", ["phash"])


def downgrade() -> None:
    op.drop_index("idx_gi_phash", table_name="gallery_images")
    op.drop_column("gallery_images", "phash")
    op.drop_index("idx_gallery_dupgroup", table_name="galleries")
    op.drop_index("idx_gallery_content_hash", table_name="galleries")
    op.drop_column("galleries", "dedup_status")
    op.drop_column("galleries", "duplicate_group")
    op.drop_column("galleries", "content_hash")
    op.drop_column("media_items", "dedup_status")
    op.drop_table("media_frame_hashes")
