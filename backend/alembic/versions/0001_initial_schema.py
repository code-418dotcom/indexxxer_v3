"""Initial schema

Revision ID: 8e3f1a5b2d9c
Revises:
Create Date: 2026-03-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8e3f1a5b2d9c"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── media_sources ──────────────────────────────────────────────────────────
    op.create_table(
        "media_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="local"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("scan_config", postgresql.JSONB(), nullable=True),
        sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # ── tags ───────────────────────────────────────────────────────────────────
    op.create_table(
        "tags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_tag_slug"),
    )
    op.create_index("idx_tag_category", "tags", ["category"])
    op.create_index("idx_tag_name", "tags", ["name"])

    # ── media_items ────────────────────────────────────────────────────────────
    op.create_table(
        "media_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(36),
            sa.ForeignKey("media_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # File identity
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=True, unique=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("file_mtime", sa.DateTime(timezone=True), nullable=True),
        # Classification
        sa.Column("media_type", sa.String(20), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        # Stream info
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("codec", sa.String(50), nullable=True),
        sa.Column("frame_rate", sa.Float(), nullable=True),
        # Derived assets
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.Column("preview_path", sa.Text(), nullable=True),
        # Status
        sa.Column(
            "index_status",
            sa.String(30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        # Full-text search
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("source_id", "file_path", name="uq_source_path"),
    )
    op.create_index(
        "idx_media_fts",
        "media_items",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index("idx_media_hash", "media_items", ["file_hash"])
    op.create_index("idx_media_type", "media_items", ["media_type"])
    op.create_index("idx_media_source", "media_items", ["source_id"])
    op.create_index("idx_media_status", "media_items", ["index_status"])
    op.create_index("idx_media_mtime", "media_items", ["file_mtime"])
    op.create_index("idx_media_indexed_at", "media_items", ["indexed_at"])

    # ── tsvector update trigger ────────────────────────────────────────────────
    # Keeps search_vector in sync whenever filename or mime_type changes.
    # Tag names are appended by the tagging worker (Phase 3+) to avoid lock
    # contention during bulk operations.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_media_search_vector()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.filename, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.mime_type, '')), 'C');
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_media_search_vector
            BEFORE INSERT OR UPDATE OF filename, mime_type
            ON media_items
            FOR EACH ROW EXECUTE FUNCTION update_media_search_vector();
        """
    )

    # ── media_tags ─────────────────────────────────────────────────────────────
    op.create_table(
        "media_tags",
        sa.Column(
            "media_id",
            sa.String(36),
            sa.ForeignKey("media_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.String(36),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "source",
            sa.String(30),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_media_tags_tag", "media_tags", ["tag_id"])

    # ── index_jobs ─────────────────────────────────────────────────────────────
    op.create_table(
        "index_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(36),
            sa.ForeignKey("media_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_type",
            sa.String(30),
            nullable=False,
            server_default="full",
        ),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("total_files", sa.Integer(), nullable=True),
        sa.Column(
            "processed_files",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "failed_files",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "skipped_files",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_job_source", "index_jobs", ["source_id"])
    op.create_index("idx_job_status", "index_jobs", ["status"])

    # ── saved_filters ──────────────────────────────────────────────────────────
    # M2 feature; schema defined now to avoid a breaking migration later.
    op.create_table(
        "saved_filters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("saved_filters")

    op.drop_index("idx_job_status", table_name="index_jobs")
    op.drop_index("idx_job_source", table_name="index_jobs")
    op.drop_table("index_jobs")

    op.drop_index("idx_media_tags_tag", table_name="media_tags")
    op.drop_table("media_tags")

    # Drop trigger + function before dropping the table
    op.execute("DROP TRIGGER IF EXISTS trg_media_search_vector ON media_items")
    op.execute("DROP FUNCTION IF EXISTS update_media_search_vector")

    op.drop_index("idx_media_indexed_at", table_name="media_items")
    op.drop_index("idx_media_mtime", table_name="media_items")
    op.drop_index("idx_media_status", table_name="media_items")
    op.drop_index("idx_media_source", table_name="media_items")
    op.drop_index("idx_media_type", table_name="media_items")
    op.drop_index("idx_media_hash", table_name="media_items")
    op.drop_index("idx_media_fts", table_name="media_items")
    op.drop_table("media_items")

    op.drop_index("idx_tag_name", table_name="tags")
    op.drop_index("idx_tag_category", table_name="tags")
    op.drop_table("tags")

    op.drop_table("media_sources")
