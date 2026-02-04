import pytest
from airwave.core.db import engine, get_db, init_db
from sqlalchemy import text


@pytest.mark.asyncio
async def test_db_connection_and_wal():
    """Verify DB connection and WAL mode."""
    # Ensure tables are created
    await init_db()

    async with engine.connect() as conn:
        # Check Journal Mode
        result = await conn.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
        assert mode.upper() == "WAL"

        # Check Synchronous Mode
        result = await conn.execute(text("PRAGMA synchronous"))
        sync_mode = result.scalar()
        # synchronous=NORMAL is usually 1
        assert sync_mode == 1


@pytest.mark.asyncio
async def test_session_factory():
    """Verify session dependency."""
    async for session in get_db():
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
