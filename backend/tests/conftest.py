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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set a test API token BEFORE importing app modules so Settings picks it up
os.environ.setdefault("API_TOKEN", "test-token-insecure")

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
import app.models  # noqa: E402, F401  — register all models with Base.metadata

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
# Function scope is simplest with pytest-asyncio auto mode and avoids
# event-loop lifetime issues with session-scoped async fixtures.
# Schema creation is fast (< 1s); no real-media data is loaded in tests.
@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
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
            yield session
            await session.rollback()


# ── HTTP test client with dependency overrides ─────────────────────────────────
@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """
    AsyncClient wired to the FastAPI app.
    - Overrides get_db to use the test session.
    - Sends the test API token on every request.
    """
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Token": "test-token-insecure"},
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


# ── Convenience header dict for manual requests ────────────────────────────────
AUTH_HEADERS = {"X-API-Token": "test-token-insecure"}
