import asyncio
from sqlalchemy import select
from airwave.core.db import AsyncSessionLocal
from airwave.core.models import Track, ArtistAlias

async def check_casing():
    async with AsyncSessionLocal() as session:
        print("Checking Track table artists casing:")
        res = await session.execute(select(Track).limit(10))
        tracks = res.scalars().all()
        for t in tracks:
            print(f"  - '{t.artist}' (islower: {t.artist.islower() if t.artist else 'N/A'})")
            
        print("\nChecking ArtistAlias table:")
        res = await session.execute(select(ArtistAlias).limit(10))
        aliases = res.scalars().all()
        for a in aliases:
            print(f"  - raw: '{a.raw_name}' -> resolved: '{a.resolved_name}'")

if __name__ == "__main__":
    asyncio.run(check_casing())
