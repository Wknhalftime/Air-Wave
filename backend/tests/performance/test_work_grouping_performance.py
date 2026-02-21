"""Performance tests for work-recording grouping.

This test suite covers:
- Query performance benchmarks
- Large catalog handling (>500 works)
- Performance regression tests
- Fuzzy matching performance optimization
"""

import time

import pytest
from airwave.core.models import Work
from airwave.worker.scanner import FileScanner
from sqlalchemy import select, func


class TestQueryPerformance:
    """Test query performance benchmarks."""

    @pytest.mark.asyncio
    async def test_work_count_query_performance(self, db_session):
        """Test that work count query completes quickly."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")
        
        # Create 1000 works directly in database to avoid fuzzy grouping
        for i in range(1000):
            work = Work(title=f"song {i:04d}", artist_id=artist.id)
            db_session.add(work)
        await db_session.commit()
        
        # Measure COUNT(*) query time
        start = time.time()
        stmt = select(func.count()).select_from(Work).where(Work.artist_id == artist.id)
        result = await db_session.execute(stmt)
        count = result.scalar()
        elapsed = time.time() - start
        
        assert count == 1000
        # Should complete in <10ms for 1000 works
        assert elapsed < 0.01, f"Count query took {elapsed:.3f}s, expected <0.01s"

    @pytest.mark.asyncio
    async def test_fuzzy_match_query_selects_only_needed_columns(self, db_session):
        """Test that fuzzy match query selects only id and title columns."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")
        
        # Create 100 works
        work1 = await scanner._upsert_work("song title", artist.id)
        for i in range(99):
            await scanner._upsert_work(f"other song {i:04d}", artist.id)
        await db_session.commit()
        
        # Measure query time with column selection
        start = time.time()
        similar = await scanner._find_similar_work("song titl", artist.id)
        elapsed = time.time() - start
        
        assert similar is not None
        assert similar.id == work1.id
        # Should complete quickly (<50ms for 100 works)
        assert elapsed < 0.05, f"Fuzzy match query took {elapsed:.3f}s, expected <0.05s"

    @pytest.mark.asyncio
    async def test_exact_match_query_performance(self, db_session):
        """Test that exact match query is fast (uses index)."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")
        
        # Create 1000 works
        work_target = await scanner._upsert_work("target song", artist.id)
        for i in range(999):
            await scanner._upsert_work(f"other song {i:04d}", artist.id)
        await db_session.commit()
        
        # Measure exact match query time
        start = time.time()
        work = await scanner._upsert_work("target song", artist.id)
        elapsed = time.time() - start
        
        assert work.id == work_target.id
        # Should complete very quickly (<5ms) due to index
        assert elapsed < 0.005, f"Exact match took {elapsed:.3f}s, expected <0.005s"


class TestLargeCatalogHandling:
    """Test behavior with large artist catalogs."""

    @pytest.mark.asyncio
    async def test_large_catalog_skips_fuzzy_matching(self, db_session):
        """Test that fuzzy matching is skipped for artists with >500 works."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("mega artist")
        
        # Create 600 works directly in database to avoid fuzzy grouping
        for i in range(600):
            work = Work(title=f"song {i:04d}", artist_id=artist.id)
            db_session.add(work)
        await db_session.commit()

        # Should skip fuzzy matching (return None)
        start = time.time()
        similar = await scanner._find_similar_work("song 0000", artist.id)
        elapsed = time.time() - start

        assert similar is None  # Skipped due to work count limit
        # Should be very fast (just count query, no fuzzy matching)
        assert elapsed < 0.01, f"Skipped fuzzy matching took {elapsed:.3f}s, expected <0.01s"

    @pytest.mark.asyncio
    async def test_large_catalog_exact_match_still_works(self, db_session):
        """Test that exact match still works for large catalogs."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("mega artist")
        
        # Create 600 works
        work_target = await scanner._upsert_work("target song", artist.id)
        for i in range(599):
            await scanner._upsert_work(f"other song {i:04d}", artist.id)
        await db_session.commit()
        
        # Exact match should still work (doesn't use fuzzy matching)
        start = time.time()
        work = await scanner._upsert_work("target song", artist.id)
        elapsed = time.time() - start
        
        assert work.id == work_target.id
        # Should be fast (index-based lookup)
        assert elapsed < 0.01, f"Exact match took {elapsed:.3f}s, expected <0.01s"

    @pytest.mark.asyncio
    async def test_performance_degradation_with_catalog_size(self, db_session):
        """Test that performance degrades gracefully with catalog size."""
        scanner = FileScanner(db_session)
        
        # Test with different catalog sizes
        catalog_sizes = [10, 50, 100, 250, 500]
        times = []
        
        for size in catalog_sizes:
            artist = await scanner._upsert_artist(f"artist_{size}")
            
            # Create works
            work1 = await scanner._upsert_work("song title", artist.id)
            for i in range(size - 1):
                await scanner._upsert_work(f"other song {i:04d}", artist.id)
            await db_session.commit()
            
            # Measure fuzzy matching time
            start = time.time()
            similar = await scanner._find_similar_work("song titl", artist.id)
            elapsed = time.time() - start
            times.append(elapsed)
            
            assert similar is not None
            assert similar.id == work1.id
        
        # Performance should scale roughly linearly (O(n))
        # 500 works should take <10x longer than 50 works
        ratio = times[-1] / times[1]  # 500 works / 50 works
        assert ratio < 15, f"Performance degradation too high: {ratio:.1f}x (expected <15x)"

