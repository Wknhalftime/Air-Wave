from pathlib import Path

import pytest
from airwave.api.deps import get_db
from airwave.api.main import app
from airwave.core.db import Base
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# event_loop fixture removed (deprecated in pytest-asyncio)

# ============================================================================
# TEST DATABASE CONFIGURATION
# ============================================================================
# CRITICAL: Tests use a SEPARATE database to avoid destroying production data
# Test database: backend/data/airwave_test.db
# Production database: backend/data/airwave.db
# ============================================================================

# Get test database path
TEST_DB_PATH = Path(__file__).parent.parent / "data" / "airwave_test.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

# Create test-specific engine (NEVER use production engine in tests!)
test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
)

# Create test-specific session factory
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture(scope="function")
async def db_engine():
    """Create test database tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def db_session(db_engine):
    """Provide a test database session."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session):
    """Create an async test client with DB override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def async_client(client):
    return client
