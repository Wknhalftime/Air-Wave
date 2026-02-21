from pathlib import Path

import pytest
from airwave.api.deps import get_db
from airwave.api.main import app
from airwave.core.cache import cache
from airwave.core.db import Base
# Import all models to ensure Base.metadata is populated
from airwave.core import models  # noqa
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
from sqlalchemy.pool import StaticPool

# Get test database path
# TEST_DB_PATH = Path(__file__).parent.parent / "data" / "airwave_test.db"
# TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
# Use in-memory DB for better isolation and speed
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# Create test-specific engine (NEVER use production engine in tests!)
test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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
    # Clear cache before each test to prevent cross-test contamination
    cache.clear()

    # Drop all tables first to ensure clean state
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    # Clean up after test
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


def pytest_ignore_collect(path, config):
    """Ignore standalone scripts in tests directory during pytest collection.
    
    Note: pytest 8.x still uses 'path' (py.path.local) but will transition to
    'collection_path' (pathlib.Path) in pytest 9.x.
    """
    # Handle py.path.local (pytest 8.x) - uses .basename
    # Will also work with pathlib.Path (pytest 9.x) - uses .name
    if hasattr(path, 'basename'):
        # py.path.local (current pytest 8.x API)
        filename = path.basename
    elif hasattr(path, 'name'):
        # pathlib.Path (future pytest 9.x API)
        filename = path.name
    else:
        # Fallback: convert to string and extract filename
        filename = str(path).split('/')[-1].split('\\')[-1]
    
    if filename == "load_test.py":
        return True
    return None
