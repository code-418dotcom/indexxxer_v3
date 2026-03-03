"""
ORM model registry.
Import all models here so Alembic's autogenerate picks them up.
"""

from app.models.base import Base  # noqa: F401
from app.models.gallery import Gallery, GalleryImage  # noqa: F401
from app.models.pdf_document import PDFDocument  # noqa: F401
from app.models.index_job import IndexJob  # noqa: F401
from app.models.media_face import MediaFace  # noqa: F401
from app.models.media_item import MediaItem  # noqa: F401
from app.models.media_source import MediaSource  # noqa: F401
from app.models.saved_filter import SavedFilter  # noqa: F401
from app.models.query_log import QueryLog  # noqa: F401
from app.models.source_credential import SourceCredential  # noqa: F401
from app.models.tag import MediaTag, Tag  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.webhook import Webhook, WebhookDelivery  # noqa: F401
