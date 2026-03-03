"""M3 AI pipeline — captions, transcripts, summaries, face detection

Revision ID: b3d5f7a9c1e2
Revises: a2c4e6f8b0d1
Create Date: 2026-03-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3d5f7a9c1e2"
down_revision: Union[str, None] = "a2c4e6f8b0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New columns on media_items ─────────────────────────────────────────────
    op.add_column("media_items", sa.Column("caption", sa.Text(), nullable=True))
    op.add_column(
        "media_items",
        sa.Column("caption_status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.add_column("media_items", sa.Column("transcript", sa.Text(), nullable=True))
    op.add_column(
        "media_items",
        sa.Column("transcript_status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.add_column("media_items", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "media_items",
        sa.Column("summary_status", sa.String(20), nullable=False, server_default="pending"),
    )

    # ── New table: media_faces ─────────────────────────────────────────────────
    # media_items.id is VARCHAR(36) — media_id must match to satisfy the FK
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS media_faces (
            id          VARCHAR(36) PRIMARY KEY,
            media_id    VARCHAR(36) NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
            cluster_id  INTEGER,
            bbox_x      INTEGER NOT NULL,
            bbox_y      INTEGER NOT NULL,
            bbox_w      INTEGER NOT NULL,
            bbox_h      INTEGER NOT NULL,
            embedding   vector(512),
            confidence  FLOAT NOT NULL,
            created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_faces_media ON media_faces(media_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_faces_cluster ON media_faces(cluster_id)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_faces_embedding ON media_faces
            USING hnsw (embedding vector_cosine_ops)
            WITH (m=16, ef_construction=64)
        """
    )

    # ── Update search_vector trigger to include caption + transcript ───────────
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION update_media_search_vector()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english',
                    coalesce(regexp_replace(NEW.filename, '\.[^.]+$', ''), '')), 'A') ||
                setweight(to_tsvector('english',
                    coalesce(NEW.caption, '')), 'B') ||
                setweight(to_tsvector('english',
                    coalesce(NEW.transcript, '')), 'B') ||
                setweight(to_tsvector('english',
                    coalesce(split_part(NEW.mime_type, '/', 2), '')), 'C');
            RETURN NEW;
        END;
        $$;
        """
    )

    # Also fire the trigger on updates to caption and transcript columns
    op.execute("DROP TRIGGER IF EXISTS tsvector_update ON media_items")
    op.execute(
        """
        CREATE TRIGGER tsvector_update
            BEFORE INSERT OR UPDATE OF filename, mime_type, caption, transcript
            ON media_items
            FOR EACH ROW EXECUTE FUNCTION update_media_search_vector()
        """
    )

    # ── Backfill existing rows with the updated trigger output ─────────────────
    op.execute(
        r"""
        UPDATE media_items SET
            search_vector =
                setweight(to_tsvector('english',
                    coalesce(regexp_replace(filename, '\.[^.]+$', ''), '')), 'A') ||
                setweight(to_tsvector('english',
                    coalesce(caption, '')), 'B') ||
                setweight(to_tsvector('english',
                    coalesce(transcript, '')), 'B') ||
                setweight(to_tsvector('english',
                    coalesce(split_part(mime_type, '/', 2), '')), 'C')
        """
    )


def downgrade() -> None:
    # Restore the M2 trigger (filename + mime only)
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
    op.execute("DROP TRIGGER IF EXISTS tsvector_update ON media_items")
    op.execute(
        """
        CREATE TRIGGER tsvector_update
            BEFORE INSERT OR UPDATE OF filename, mime_type
            ON media_items
            FOR EACH ROW EXECUTE FUNCTION update_media_search_vector()
        """
    )

    op.execute("DROP INDEX IF EXISTS idx_faces_embedding")
    op.execute("DROP INDEX IF EXISTS idx_faces_cluster")
    op.execute("DROP INDEX IF EXISTS idx_faces_media")
    op.execute("DROP TABLE IF EXISTS media_faces")

    op.drop_column("media_items", "summary_status")
    op.drop_column("media_items", "summary")
    op.drop_column("media_items", "transcript_status")
    op.drop_column("media_items", "transcript")
    op.drop_column("media_items", "caption_status")
    op.drop_column("media_items", "caption")
