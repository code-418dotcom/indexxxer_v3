"""
Shared pytest fixtures for the indexxxer test suite.

Requires a running PostgreSQL instance with an `indexxxer_test` database.
Create it once:
    psql -U indexxxer -c "CREATE DATABASE indexxxer_test;"

The test database URL is resolved from (in order):
  1. TEST_DATABASE_URL environment variable
  2. DATABASE_URL with the db name replaced by indexxxer_test
  3. Hardcoded localhost fallback

Tables are created fresh at the start of each test session and dropped at the end.
Each test runs inside a transaction that is rolled back, leaving the DB clean.
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force the test API token BEFORE importing app modules so Settings picks it up.
os.environ["API_TOKEN"] = "test-token-insecure"
# Use a well-known JWT secret in tests so we can sign tokens
os.environ["JWT_SECRET"] = "test-jwt-secret-insecure"
os.environ["ADMIN_EMAIL"] = "admin@test.local"
os.environ["ADMIN_PASSWORD"] = "testpassword"

from app.database import get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.base import Base  # noqa: E402
import app.models  # noqa: E402, F401  — register all models with Base.metadata

# Alias so the rest of the file can use `app` as the FastAPI instance
app = fastapi_app

# ── Test database URL ──────────────────────────────────────────────────────────
def _build_test_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://indexxxer:indexxxer_dev@localhost:5432/indexxxer",
    )
    # Replace the database name at the end of the URL
    if db_url.endswith("/indexxxer"):
        return db_url[: -len("indexxxer")] + "indexxxer_test"
    return db_url + "_test"


TEST_DATABASE_URL = _build_test_url()

# ── Per-test engine + schema ───────────────────────────────────────────────────
@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Install extensions (no-op if already present or unavailable)
        for ext in ("vector", "pg_trgm"):
            try:
                await conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
            except Exception:
                pass
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ── Per-test session with automatic rollback ───────────────────────────────────
@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncSession:
    """
    Each test gets an isolated database session.
    Changes are rolled back after the test regardless of outcome.
    """
    Session = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with Session() as session:
        async with session.begin():
            # Seed admin user so auth flows work in tests
            from app.services import user_service
            await user_service.seed_admin(session)
            yield session
            await session.rollback()


# ── Auth token fixture ─────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def auth_token(db_session: AsyncSession) -> str:
    """Return a valid JWT access token for the test admin user."""
    from app.config import settings
    from app.services import user_service
    from app.core.security import create_access_token

    admin = await user_service.get_by_email(db_session, settings.admin_email)
    assert admin is not None, "Admin user not seeded"
    return create_access_token(admin.id, admin.role)


# ── HTTP test client with dependency overrides ─────────────────────────────────
@pytest_asyncio.fixture
async def client(db_session: AsyncSession, auth_token: str) -> AsyncClient:
    """
    AsyncClient wired to the FastAPI app.
    - Overrides get_db to use the test session.
    - Sends a valid JWT Bearer token on every request.
    - Also accepts the static API token for backward-compat tests.
    """
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


# ── Expose the FastAPI app instance as a fixture ──────────────────────────────
@pytest.fixture
def fastapi_app():
    """Return the FastAPI app instance for tests that need direct access."""
    return app


# ── Convenience header dict for manual requests ────────────────────────────────
AUTH_HEADERS: dict[str, str] = {}  # Populated after auth_token fixture resolves


@pytest_asyncio.fixture(autouse=True)
async def _set_auth_headers(auth_token: str):
    """Keep AUTH_HEADERS dict in sync with the current test token."""
    AUTH_HEADERS.clear()
    AUTH_HEADERS["Authorization"] = f"Bearer {auth_token}"
