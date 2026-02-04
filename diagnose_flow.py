import asyncio
from airwave.core.db import AsyncSessionLocal
from airwave.core.models import Track
from airwave.worker.matcher import Matcher
from airwave.worker.identity_resolver import IdentityResolver

async def diagnose_flow():
    async with AsyncSessionLocal() as session:
        # 1. Setup Matcher and Resolver
        matcher = Matcher(session)
        resolver = IdentityResolver(session)
        
        # 2. Get a known track for baseline
        from sqlalchemy import select
        stmt = select(Track).limit(1)
        res = await session.execute(stmt)
        track = res.scalar_one_or_none()
        
        if not track:
            print("No tracks for testing.")
            return
            
        print(f"Testing Flow for Track: {track.artist} | {track.title}")
        
        # 3. Simulate Importer Logic
        # Case A: Exact match (uppercase)
        raw_artist = track.artist.upper()
        raw_title = track.title
        
        # Step i: Resolve
        resolved_map = await resolver.resolve_batch([raw_artist])
        resolved_artist = resolved_map.get(raw_artist, raw_artist)
        print(f"  Step 1 (Resolve): {raw_artist} -> {resolved_artist}")
        
        # Step ii: Match Batch
        queries = [(resolved_artist, raw_title)]
        match_results = await matcher.match_batch(queries)
        print(f"  Step 2 (Match Batch): Found keys {list(match_results.keys())}")
        
        # Step iii: Key Lookup (The 'Importer' step)
        result = match_results.get((resolved_artist, raw_title))
        if result:
            print(f"  Step 3 (Lookup): SUCCESS. ID: {result[0]}, Reason: {result[1]}")
        else:
            print(f"  Step 3 (Lookup): FAILURE. Key not found in results.")

        # Case B: Heuristic Split detection
        split_artist = "SLASH F/MYLES KENNEDY"
        print(f"\nTesting Flow for Potential Split: {split_artist}")
        
        # Step i: Resolve
        resolved_map = await resolver.resolve_batch([split_artist])
        resolved_artist = resolved_map.get(split_artist, split_artist)
        print(f"  Step 1 (Resolve): {split_artist} -> {resolved_artist}")
        
        # Step ii: Match Batch
        queries = [(resolved_artist, raw_title)]
        match_results = await matcher.match_batch(queries)
        print(f"  Step 2 (Match Batch Result): {match_results.get((resolved_artist, raw_title))}")

if __name__ == "__main__":
    asyncio.run(diagnose_flow())
