import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "src")))

from airwave.core.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    print("Verifying database schema...")
    async with AsyncSessionLocal() as db:
        # Check tables
        result = await db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='verification_audit';"))
        if result.scalar():
            print("SUCCESS: verification_audit table exists.")
        else:
            print("FAILURE: verification_audit table MISSING.")

        # Check column
        try:
            # Check if column exists by selecting it (sqlite doesn't have robust information_schema)
            # We select from identity_bridge where 1=0 just to check if the column is recognized
            await db.execute(text("SELECT is_revoked FROM identity_bridge LIMIT 0;"))
            print("SUCCESS: is_revoked column exists.")
        except Exception as e:
            print(f"FAILURE: is_revoked column error: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
