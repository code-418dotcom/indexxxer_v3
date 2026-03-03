"""PDF documents table

Revision ID: h9i1b3d5f7g8
Revises: g8h0a2c4e6f7
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h9i1b3d5f7g8"
down_revision: Union[str, None] = "g8h0a2c4e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pdf_documents (
            id           VARCHAR(36) PRIMARY KEY,
            source_id    VARCHAR(36) REFERENCES media_sources(id) ON DELETE SET NULL,
            file_path    TEXT        NOT NULL UNIQUE,
            filename     VARCHAR(512) NOT NULL,
            title        TEXT,
            page_count   INTEGER     NOT NULL DEFAULT 0,
            cover_path   TEXT,
            file_size    BIGINT,
            file_mtime   TIMESTAMPTZ,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_pdf_source ON pdf_documents(source_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pdf_mtime  ON pdf_documents(file_mtime)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pdf_mtime")
    op.execute("DROP INDEX IF EXISTS idx_pdf_source")
    op.execute("DROP TABLE IF EXISTS pdf_documents")
