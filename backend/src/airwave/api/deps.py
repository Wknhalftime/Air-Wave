from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from airwave.core.db import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
