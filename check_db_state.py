import asyncio
from airwave.core.db import AsyncSessionLocal
from airwave.core.models import BroadcastLog, ImportBatch, Track
from sqlalchemy import select, func

async def check():
    async with AsyncSessionLocal() as session:
        # Logs count
        log_count = (await session.execute(select(func.count(BroadcastLog.id)))).scalar()
        print(f"Total Broadcast Logs: {log_count}")
        
        # Track count
        track_count = (await session.execute(select(func.count(Track.id)))).scalar()
        real_tracks = (await session.execute(select(func.count(Track.id)).where(~Track.path.contains('virtual://')))).scalar()
        print(f"Total Tracks: {track_count} ({real_tracks} with real files)")
        
        # Batches
        result = await session.execute(select(ImportBatch).order_by(ImportBatch.id.desc()).limit(5))
        batches = result.scalars().all()
        print("\nLast 5 Import Batches:")
        for b in batches:
            print(f"  - {b.filename}: {b.status} ({b.processed_rows}/{b.total_rows} rows)")
            if b.error_log:
                print(f"    Error: {b.error_log}")

if __name__ == "__main__":
    asyncio.run(check())
