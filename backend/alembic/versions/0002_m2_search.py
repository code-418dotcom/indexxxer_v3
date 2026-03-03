"""M2 search — pgvector, pg_trgm, CLIP embedding, favourites, trigger fix

Revision ID: a2c4e6f8b0d1
Revises: 8e3f1a5b2d9c
Create Date: 2026-03-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2c4e6f8b0d1"
down_revision: Union[str, None] = "8e3f1a5b2d9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── New columns on media_items ─────────────────────────────────────────────
    # clip_embedding is vector(768) — nullable until computed by GPU worker
    op.execute("ALTER TABLE media_items ADD COLUMN IF NOT EXISTS clip_embedding vector(768)")
    op.add_column(
        "media_items",
        sa.Column(
            "clip_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "media_items",
        sa.Column(
            "is_favourite",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ── HNSW index for cosine similarity (pgvector ANN) ───────────────────────
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_media_clip_embedding
            ON media_items USING hnsw (clip_embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """
    )

    # ── Trigram index for fuzzy filename search ────────────────────────────────
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_media_filename_trgm
            ON media_items USING GIN (filename gin_trgm_ops)
        """
    )

    # ── Fix tsvector trigger: strip file extension + mime type prefix ─────────
    # Before: 'sunset.jpg' → 'sunset.jpg', 'image/jpeg' → 'image/jpeg' (useless)
    # After:  'sunset.jpg' → 'sunset', 'image/jpeg' → 'jpeg'
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION update_media_search_vector()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english',
                    coalesce(regexp_replace(NEW.filename, '\.[^.]+$', ''), '')), 'A') ||
                setweight(to_tsvector('english',
                    coalesce(split_part(NEW.mime_type, '/', 2), '')), 'C');
            RETURN NEW;
        END;
        $$;
        """
    )

    # ── Backfill existing rows with the fixed search_vector ───────────────────
    op.execute(
        r"""
        UPDATE media_items SET
            search_vector =
                setweight(to_tsvector('english',
                    coalesce(regexp_replace(filename, '\.[^.]+$', ''), '')), 'A') ||
                setweight(to_tsvector('english',
                    coalesce(split_part(mime_type, '/', 2), '')), 'C')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_media_clip_embedding")
    op.execute("DROP INDEX IF EXISTS idx_media_filename_trgm")
    op.execute("ALTER TABLE media_items DROP COLUMN IF EXISTS clip_embedding")
    op.drop_column("media_items", "is_favourite")
    op.drop_column("media_items", "clip_status")
    # Extensions intentionally left — other objects may depend on them
