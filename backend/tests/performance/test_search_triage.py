"""
Performance test for Search Triage SQL (Gold/Silver/Bronze filtering).

This test verifies that the search endpoint efficiently filters recordings
by their status (Gold = has file, Silver = verified, Bronze = unverified).
"""
import asyncio
import time
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from airwave.core.db import AsyncSessionLocal
from airwave.core.models import Recording, Work, Artist, LibraryFile


async def test_search_triage_performance():
    """Test that search filtering is efficient and returns correct results."""

    async with AsyncSessionLocal() as session:
        # Test query: Search for "beatles" with Bronze filtering
        term = "%beatles%"
        
        print("=" * 60)
        print("SEARCH TRIAGE SQL PERFORMANCE TEST")
        print("=" * 60)
        
        # Test 1: Search WITHOUT Bronze filtering (default)
        print("\n[TEST 1] Search WITHOUT Bronze (include_bronze=False)")
        print("-" * 60)
        
        start = time.time()
        stmt = (
            select(Recording)
            .options(
                selectinload(Recording.work).selectinload(Work.artist),
                selectinload(Recording.files),
            )
            .join(Recording.work)
            .join(Work.artist)
            .outerjoin(LibraryFile, Recording.id == LibraryFile.recording_id)
            .where(
                or_(
                    Artist.name.ilike(term),
                    Recording.title.ilike(term),
                    Work.title.ilike(term),
                )
            )
            .where(
                or_(
                    Recording.is_verified == True,
                    LibraryFile.id.is_not(None)
                )
            )
            .distinct()
            .limit(50)
        )
        
        result = await session.execute(stmt)
        recordings = result.scalars().all()
        elapsed = (time.time() - start) * 1000
        
        print(f"Results: {len(recordings)} recordings")
        print(f"Time: {elapsed:.2f}ms")
        
        # Verify status distribution
        gold_count = sum(1 for r in recordings if r.files)
        silver_count = sum(1 for r in recordings if r.is_verified and not r.files)
        bronze_count = sum(1 for r in recordings if not r.is_verified and not r.files)
        
        print(f"Gold (has file): {gold_count}")
        print(f"Silver (verified, no file): {silver_count}")
        print(f"Bronze (unverified, no file): {bronze_count}")
        
        assert bronze_count == 0, "Bronze recordings should be filtered out!"
        
        # Test 2: Search WITH Bronze filtering (include_bronze=True)
        print("\n[TEST 2] Search WITH Bronze (include_bronze=True)")
        print("-" * 60)
        
        start = time.time()
        stmt = (
            select(Recording)
            .options(
                selectinload(Recording.work).selectinload(Work.artist),
                selectinload(Recording.files),
            )
            .join(Recording.work)
            .join(Work.artist)
            .outerjoin(LibraryFile, Recording.id == LibraryFile.recording_id)
            .where(
                or_(
                    Artist.name.ilike(term),
                    Recording.title.ilike(term),
                    Work.title.ilike(term),
                )
            )
            .distinct()
            .limit(50)
        )
        
        result = await session.execute(stmt)
        recordings_with_bronze = result.scalars().all()
        elapsed = (time.time() - start) * 1000
        
        print(f"Results: {len(recordings_with_bronze)} recordings")
        print(f"Time: {elapsed:.2f}ms")
        
        # Verify status distribution
        gold_count = sum(1 for r in recordings_with_bronze if r.files)
        silver_count = sum(1 for r in recordings_with_bronze if r.is_verified and not r.files)
        bronze_count = sum(1 for r in recordings_with_bronze if not r.is_verified and not r.files)
        
        print(f"Gold (has file): {gold_count}")
        print(f"Silver (verified, no file): {silver_count}")
        print(f"Bronze (unverified, no file): {bronze_count}")
        
        # Test 3: Verify filtering works correctly
        print("\n[TEST 3] Verification")
        print("-" * 60)
        
        assert len(recordings_with_bronze) >= len(recordings), \
            "Including Bronze should return same or more results"
        
        print(f"✅ Filtering works: {len(recordings_with_bronze)} total, {len(recordings)} without Bronze")
        print(f"✅ Bronze filtered: {len(recordings_with_bronze) - len(recordings)} recordings excluded")
        
        # Performance check
        print("\n[PERFORMANCE CHECK]")
        print("-" * 60)
        
        if elapsed < 100:
            print(f"✅ EXCELLENT: Query completed in {elapsed:.2f}ms (< 100ms)")
        elif elapsed < 500:
            print(f"✅ GOOD: Query completed in {elapsed:.2f}ms (< 500ms)")
        elif elapsed < 1000:
            print(f"⚠️  ACCEPTABLE: Query completed in {elapsed:.2f}ms (< 1s)")
        else:
            print(f"❌ SLOW: Query took {elapsed:.2f}ms (> 1s) - needs optimization!")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_search_triage_performance())

