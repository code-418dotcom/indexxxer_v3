"""Gallery feature — galleries + gallery_images tables

Revision ID: g8h0a2c4e6f7
Revises: f7a9c1e3g5i6
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g8h0a2c4e6f7"
down_revision: Union[str, None] = "f7a9c1e3g5i6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS galleries (
            id           VARCHAR(36) PRIMARY KEY,
            source_id    VARCHAR(36) REFERENCES media_sources(id) ON DELETE SET NULL,
            file_path    TEXT        NOT NULL UNIQUE,
            filename     VARCHAR(512) NOT NULL,
            image_count  INTEGER     NOT NULL DEFAULT 0,
            cover_path   TEXT,
            file_size    BIGINT,
            file_mtime   TIMESTAMPTZ,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_gallery_source ON galleries(source_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_gallery_mtime  ON galleries(file_mtime)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS gallery_images (
            id           VARCHAR(36) PRIMARY KEY,
            gallery_id   VARCHAR(36) NOT NULL REFERENCES galleries(id) ON DELETE CASCADE,
            filename     TEXT        NOT NULL,
            index_order  INTEGER     NOT NULL,
            width        INTEGER,
            height       INTEGER
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_gi_gallery ON gallery_images(gallery_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_gi_order ON gallery_images(gallery_id, index_order)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_gi_order")
    op.execute("DROP INDEX IF EXISTS idx_gi_gallery")
    op.execute("DROP TABLE IF EXISTS gallery_images")
    op.execute("DROP INDEX IF EXISTS idx_gallery_mtime")
    op.execute("DROP INDEX IF EXISTS idx_gallery_source")
    op.execute("DROP TABLE IF EXISTS galleries")
