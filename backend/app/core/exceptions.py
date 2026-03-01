"""
Structured HTTP exception helpers.

All error responses follow the shape: {"detail": "<message>"}
which is FastAPI's default. These helpers make raise sites more readable.
"""

from fastapi import HTTPException, status


def not_found(resource: str, id: str | None = None) -> HTTPException:
    detail = f"{resource} not found"
    if id:
        detail = f"{resource} '{id}' not found"
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def unprocessable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
    )
