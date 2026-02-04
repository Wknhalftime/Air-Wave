import asyncio
from sqlalchemy import select
from airwave.core.db import AsyncSessionLocal
from airwave.core.models import Track, BroadcastLog
from airwave.worker.matcher import Matcher
from airwave.worker.identity_resolver import IdentityResolver

async def diagnose():
    async with AsyncSessionLocal() as session:
        # 1. Check if we have tracks
        stmt = select(Track).limit(5)
        res = await session.execute(stmt)
        tracks = res.scalars().all()
        print(f"Tracks in DB: {len(tracks)}")
        for t in tracks:
            print(f"  - {t.artist} | {t.title} ({t.path})")

        if not tracks:
            print("ERROR: No tracks found in DB. Matcher can't work.")
            return

        # 2. Test Matcher for a known track
        matcher = Matcher(session)
        resolver = IdentityResolver(session)
        
        test_artist = tracks[0].artist.upper() # Try uppercase to test resolver/normalizer
        test_title = tracks[0].title
        
        print(f"\nTesting Match for: {test_artist} | {test_title}")
        
        # Resolve
        resolved_map = await resolver.resolve_batch([test_artist])
        resolved_artist = resolved_map.get(test_artist, test_artist)
        print(f"  Resolved Artist: {resolved_artist}")
        
        # Match
        match_id, reason = await matcher.find_match(resolved_artist, test_title)
        print(f"  Match Result: ID {match_id}, Reason: {reason}")
        
        if match_id == tracks[0].id:
            print("  SUCCESS: Exact match works.")
        else:
            print(f"  FAILURE: Expected {tracks[0].id}, got {match_id}")

        # 3. Check Broadcast Logs
        stmt = select(BroadcastLog).where(BroadcastLog.track_id == None).limit(5)
        res = await session.execute(stmt)
        unmatched = res.scalars().all()
        print(f"\nUnmatched Logs in DB: {len(unmatched)}")
        for log in unmatched:
            print(f"  - {log.raw_artist} | {log.raw_title} (Reason: {log.match_reason})")

if __name__ == "__main__":
    asyncio.run(diagnose())
