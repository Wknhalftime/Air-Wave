import asyncio
import sys
import os

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from sqlalchemy.ext.asyncio import create_async_engine
from airwave.core.config import settings
from airwave.core.models import Base

async def reset():
    print(f"Connecting to {settings.DB_URL}...")
    engine = create_async_engine(settings.DB_URL)
    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Tables dropped successfully.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reset())
