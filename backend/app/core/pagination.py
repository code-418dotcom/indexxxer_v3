"""
Offset-based pagination helpers.

Usage in a router:
    @router.get("/items")
    async def list_items(params: PaginationParams = Depends()):
        ...
        return paginate(items, total, params)
"""

from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class PaginationParams(BaseModel):
    """Injected via Depends() into route handlers."""

    page: int = Query(default=1, ge=1, description="1-based page number")
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int


def paginate(items: list[Any], total: int, params: PaginationParams) -> dict:
    """Build a PaginatedResponse-compatible dict."""
    pages = max(1, -(-total // params.limit))  # ceiling division
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "limit": params.limit,
        "pages": pages,
    }
