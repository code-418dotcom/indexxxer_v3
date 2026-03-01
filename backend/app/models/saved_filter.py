"""
Saved filter sets — M2 feature, schema defined in M1 to avoid a breaking migration.
In M1 these are global (no user ownership). A user_id FK is added in M4.
"""

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class SavedFilter(Base, TimestampMixin):
    __tablename__ = "saved_filters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Serialised FilterSet object
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
