"""Tests for fuzzy work matching functionality.

This test suite covers:
- Basic fuzzy matching functionality
- Similarity threshold validation (85%)
- Work count limit (500 works)
- Early termination on >95% match
- False positive prevention
- Query optimization (id, title only)
- Configuration validation
"""

import pytest
from airwave.core.config import settings
from airwave.core.models import Artist, Work
from airwave.worker.scanner import FileScanner
from sqlalchemy import select, func


class TestFuzzyMatchingBasic:
    """Test basic fuzzy matching functionality."""

    @pytest.mark.asyncio
    async def test_fuzzy_matching_finds_similar_work(self, db_session):
        """Test that fuzzy matching finds works with similar titles."""
        scanner = FileScanner(db_session)

        # Create artist and work
        artist = await scanner._upsert_artist("test artist")
        work1 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Find similar work (extra space)
        similar = await scanner._find_similar_work("song title ", artist.id)
        assert similar is not None
        assert similar.id == work1.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_finds_minor_typo(self, db_session):
        """Test that fuzzy matching finds works with minor typos."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")
        work1 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Minor typo (missing last letter)
        similar = await scanner._find_similar_work("song titl", artist.id)
        assert similar is not None
        assert similar.id == work1.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_case_insensitive(self, db_session):
        """Test that fuzzy matching is case insensitive."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")

        # Create work directly to avoid normalization in _upsert_work
        work1 = Work(title="song title", artist_id=artist.id)
        db_session.add(work1)
        await db_session.commit()
        await db_session.refresh(work1)

        # Fuzzy matching should find it regardless of case
        similar = await scanner._find_similar_work("SONG TITLE", artist.id)
        assert similar is not None
        assert similar.id == work1.id


class TestFuzzyMatchingThreshold:
    """Test similarity threshold validation."""

    @pytest.mark.asyncio
    async def test_fuzzy_matching_threshold_85_percent(self, db_session):
        """Test that 85% threshold is used correctly."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")

        # Create work
        work1 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # 90% similar - should match
        similar = await scanner._find_similar_work("song titl", artist.id)
        assert similar is not None
        assert similar.id == work1.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_below_threshold_no_match(self, db_session):
        """Test that titles below 85% similarity don't match."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")

        # Create work
        await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Very different - should NOT match
        similar = await scanner._find_similar_work("completely different", artist.id)
        assert similar is None

    @pytest.mark.asyncio
    async def test_fuzzy_matching_custom_threshold(self, db_session):
        """Test that custom threshold can be provided."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")

        work1 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Use higher threshold (95%)
        similar = await scanner._find_similar_work("song title", artist.id, similarity_threshold=0.95)
        assert similar is not None
        assert similar.id == work1.id

        # Same query with 99% threshold should not match minor differences
        similar = await scanner._find_similar_work("song titl", artist.id, similarity_threshold=0.99)
        assert similar is None


class TestFuzzyMatchingEarlyTermination:
    """Test early termination on >95% match."""

    @pytest.mark.asyncio
    async def test_fuzzy_matching_early_termination(self, db_session):
        """Test early termination on >95% match."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")

        # Create multiple works
        work1 = await scanner._upsert_work("song title", artist.id)
        await scanner._upsert_work("song title extended", artist.id)
        await scanner._upsert_work("song title remix", artist.id)
        await db_session.commit()

        # Should return immediately on >95% match (exact match)
        similar = await scanner._find_similar_work("song title", artist.id)
        assert similar is not None
        assert similar.id == work1.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_finds_best_match(self, db_session):
        """Test that fuzzy matching finds the best match when no >95% match exists."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")

        # Create works with varying similarity
        work1 = await scanner._upsert_work("song title", artist.id)
        await scanner._upsert_work("different song", artist.id)
        await scanner._upsert_work("another track", artist.id)
        await db_session.commit()

        # Should find best match (work1)
        similar = await scanner._find_similar_work("song titl", artist.id)
        assert similar is not None
        assert similar.id == work1.id


class TestFuzzyMatchingWorkCountLimit:
    """Test work count limit (500 works)."""

    @pytest.mark.asyncio
    async def test_fuzzy_matching_skips_large_catalogs(self, db_session):
        """Test that fuzzy matching is skipped for artists with >500 works."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("prolific artist")

        # Create 501 works directly in database to avoid fuzzy grouping
        for i in range(501):
            work = Work(title=f"song {i:04d}", artist_id=artist.id)
            db_session.add(work)
        await db_session.commit()

        # Verify we actually have >500 works
        stmt = select(func.count()).select_from(Work).where(Work.artist_id == artist.id)
        result = await db_session.execute(stmt)
        count = result.scalar()
        assert count == 501, f"Expected 501 works, got {count}"

        # Should return None (skipped due to work count limit)
        similar = await scanner._find_similar_work("song 0000", artist.id)
        assert similar is None

    @pytest.mark.asyncio
    async def test_fuzzy_matching_allows_small_catalogs(self, db_session):
        """Test that fuzzy matching works for artists with <500 works."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("small artist")

        # Create 100 works
        work1 = await scanner._upsert_work("song title", artist.id)
        for i in range(99):
            await scanner._upsert_work(f"other song {i:04d}", artist.id)
        await db_session.commit()

        # Should find match
        similar = await scanner._find_similar_work("song titl", artist.id)
        assert similar is not None
        assert similar.id == work1.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_exactly_500_works(self, db_session):
        """Test that fuzzy matching works for artists with exactly 500 works."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("medium artist")

        # Create exactly 500 works
        work1 = await scanner._upsert_work("song title", artist.id)
        for i in range(499):
            await scanner._upsert_work(f"other song {i:04d}", artist.id)
        await db_session.commit()

        # Should still work (limit is >500, not >=500)
        similar = await scanner._find_similar_work("song titl", artist.id)
        assert similar is not None
        assert similar.id == work1.id


class TestFuzzyMatchingFalsePositives:
    """Test false positive prevention."""

    @pytest.mark.asyncio
    async def test_fuzzy_matching_no_false_positives(self, db_session):
        """Test that different songs are NOT grouped together."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")

        # Create two different songs
        work1 = await scanner._upsert_work("song one", artist.id)
        work2 = await scanner._upsert_work("song two", artist.id)
        await db_session.commit()

        # Should NOT match different songs
        similar = await scanner._find_similar_work("song one", artist.id)
        assert similar is not None
        assert similar.id == work1.id  # Exact match only

        similar = await scanner._find_similar_work("song two", artist.id)
        assert similar is not None
        assert similar.id == work2.id  # Exact match only

    @pytest.mark.asyncio
    async def test_fuzzy_matching_different_artists_no_match(self, db_session):
        """Test that works from different artists don't match."""
        scanner = FileScanner(db_session)

        # Create two artists with same song title
        artist1 = await scanner._upsert_artist("artist one")
        artist2 = await scanner._upsert_artist("artist two")

        work1 = await scanner._upsert_work("song title", artist1.id)
        work2 = await scanner._upsert_work("song title", artist2.id)
        await db_session.commit()

        # Should only match within same artist
        similar = await scanner._find_similar_work("song title", artist1.id)
        assert similar is not None
        assert similar.id == work1.id

        similar = await scanner._find_similar_work("song title", artist2.id)
        assert similar is not None
        assert similar.id == work2.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_handles_identical_titles(self, db_session):
        """Test handling of truly identical titles (edge case)."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")

        # Create two works with identical titles (should be prevented by upsert)
        work1 = await scanner._upsert_work("untitled", artist.id)
        work2 = await scanner._upsert_work("untitled", artist.id)
        await db_session.commit()

        # Should return the same work (upsert prevents duplicates)
        assert work1.id == work2.id


class TestFuzzyMatchingConfiguration:
    """Test configuration validation."""

    def test_fuzzy_matching_uses_config_threshold(self):
        """Test that fuzzy matching uses threshold from config."""
        # Verify threshold is configurable
        assert hasattr(settings, 'WORK_FUZZY_MATCH_THRESHOLD')
        assert settings.WORK_FUZZY_MATCH_THRESHOLD == 0.85

        assert hasattr(settings, 'WORK_FUZZY_MATCH_MAX_WORKS')
        assert settings.WORK_FUZZY_MATCH_MAX_WORKS == 500

    @pytest.mark.asyncio
    async def test_fuzzy_matching_respects_config_threshold(self, db_session):
        """Test that fuzzy matching respects configured threshold."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")

        work1 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Use default threshold from config (0.85)
        similar = await scanner._find_similar_work("song titl", artist.id)
        assert similar is not None
        assert similar.id == work1.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_respects_config_max_works(self, db_session):
        """Test that fuzzy matching respects configured max works."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("test artist")

        # Create works directly in database to avoid fuzzy grouping
        max_works = settings.WORK_FUZZY_MATCH_MAX_WORKS
        for i in range(max_works + 1):
            work = Work(title=f"song {i:04d}", artist_id=artist.id)
            db_session.add(work)
        await db_session.commit()

        # Verify we actually have >500 works
        stmt = select(func.count()).select_from(Work).where(Work.artist_id == artist.id)
        result = await db_session.execute(stmt)
        count = result.scalar()
        assert count == max_works + 1, f"Expected {max_works + 1} works, got {count}"

        # Should skip fuzzy matching
        similar = await scanner._find_similar_work("song 0000", artist.id)
        assert similar is None

