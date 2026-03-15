"""Add performers and media_performers tables.

Revision ID: i0j2c4e6f8h9
Revises: h9i1b3d5f7g8
Create Date: 2026-03-09 00:00:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "i0j2c4e6f8h9"
down_revision = "h9i1b3d5f7g8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "performers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.String(255)),
            nullable=True,
        ),
        # Profile data
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("birthdate", sa.String(50), nullable=True),
        sa.Column("birthplace", sa.String(255), nullable=True),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("ethnicity", sa.String(100), nullable=True),
        sa.Column("hair_color", sa.String(50), nullable=True),
        sa.Column("eye_color", sa.String(50), nullable=True),
        sa.Column("height", sa.String(50), nullable=True),
        sa.Column("weight", sa.String(50), nullable=True),
        sa.Column("measurements", sa.String(50), nullable=True),
        sa.Column("years_active", sa.String(50), nullable=True),
        # Profile image
        sa.Column("profile_image_path", sa.Text, nullable=True),
        # Scraping metadata
        sa.Column("freeones_url", sa.Text, nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=True),
        # Denormalized count
        sa.Column("media_count", sa.Integer, nullable=False, server_default="0"),
        # Timestamps
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_performer_slug"),
    )
    op.create_index("idx_performer_name", "performers", ["name"])

    op.create_table(
        "media_performers",
        sa.Column(
            "media_id",
            sa.String(36),
            sa.ForeignKey("media_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "performer_id",
            sa.String(36),
            sa.ForeignKey("performers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "match_source", sa.String(30), nullable=False, server_default="manual"
        ),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_media_performers_performer", "media_performers", ["performer_id"]
    )


def downgrade() -> None:
    op.drop_table("media_performers")
    op.drop_table("performers")
