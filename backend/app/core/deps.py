"""
FastAPI dependency injection helpers.

M1: Single static API token auth.
M4: Swap `require_token` for `get_current_user` (Keycloak JWT).
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

# Accept token via either header style:
#   Authorization: Bearer <token>
#   X-API-Token: <token>
_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)


async def require_token(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer_scheme)],
    api_key: Annotated[str | None, Security(_api_key_header)],
) -> None:
    """Raise 401 if the request does not carry a valid API token."""
    token = (bearer.credentials if bearer else None) or api_key
    if not token or token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Convenience alias — use as `Depends(Auth)` in routers
Auth = Depends(require_token)
