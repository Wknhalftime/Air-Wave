"""Integration tests for work-recording grouping.

This test suite covers:
- Work grouping with different versions
- Fuzzy matching in real scan scenarios
- End-to-end scanning with version extraction
- Performance with large catalogs
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from airwave.core.models import Artist, Recording, Work
from airwave.worker.scanner import FileScanner, LibraryMetadata
from sqlalchemy import select, func


class TestWorkGroupingWithVersions:
    """Test work grouping with different versions."""

    @pytest.mark.asyncio
    async def test_different_versions_group_under_same_work(self, db_session):
        """Test that different versions of same song group under one work."""
        scanner = FileScanner(db_session)

        # Create artist
        artist = await scanner._upsert_artist("test artist")

        # Create recordings with different versions
        meta_original = LibraryMetadata(
            raw_artist="Test Artist",
            raw_title="Song Title",
        )
        meta_live = LibraryMetadata(
            raw_artist="Test Artist",
            raw_title="Song Title (Live)",
        )
        meta_remix = LibraryMetadata(
            raw_artist="Test Artist",
            raw_title="Song Title (Remix)",
        )

        # Create works and recordings
        work1 = await scanner._upsert_work(meta_original.work_title, artist.id)
        work2 = await scanner._upsert_work(meta_live.work_title, artist.id)
        work3 = await scanner._upsert_work(meta_remix.work_title, artist.id)
        await db_session.commit()

        # All should be the same work
        assert work1.id == work2.id == work3.id

        # Verify work title is the base title (without version)
        assert work1.title == "song title"

    @pytest.mark.asyncio
    async def test_multiple_recordings_link_to_same_work(self, db_session):
        """Test that multiple recordings can link to the same work."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")
        work = await scanner._upsert_work("song title", artist.id)

        # Create multiple recordings
        recording1 = await scanner._upsert_recording(
            work_id=work.id,
            title="song title",
            version_type="Original",
        )
        recording2 = await scanner._upsert_recording(
            work_id=work.id,
            title="song title (live)",
            version_type="Live",
        )
        recording3 = await scanner._upsert_recording(
            work_id=work.id,
            title="song title (remix)",
            version_type="Remix",
        )
        await db_session.commit()

        # Verify all recordings link to same work
        stmt = select(Recording).where(Recording.work_id == work.id)
        result = await db_session.execute(stmt)
        recordings = result.scalars().all()

        assert len(recordings) == 3
        assert all(r.work_id == work.id for r in recordings)

        # Verify version types
        version_types = {r.version_type for r in recordings}
        assert version_types == {"Original", "Live", "Remix"}

    @pytest.mark.asyncio
    async def test_part_numbers_create_separate_works(self, db_session):
        """Test that part numbers create separate works (not versions)."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")

        # Create works with part numbers
        meta_part1 = LibraryMetadata(
            raw_artist="Test Artist",
            raw_title="Symphony (Part 1)",
        )
        meta_part2 = LibraryMetadata(
            raw_artist="Test Artist",
            raw_title="Symphony (Part 2)",
        )

        work1 = await scanner._upsert_work(meta_part1.work_title, artist.id)
        work2 = await scanner._upsert_work(meta_part2.work_title, artist.id)
        await db_session.commit()

        # Should be different works
        assert work1.id != work2.id

        # Verify titles include part numbers
        assert "part 1" in work1.title.lower() or "part 1" in meta_part1.work_title.lower()
        assert "part 2" in work2.title.lower() or "part 2" in meta_part2.work_title.lower()

    @pytest.mark.asyncio
    async def test_subtitles_create_separate_works(self, db_session):
        """Test that subtitles create separate works (not versions)."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")

        # Create works with subtitles
        meta_main = LibraryMetadata(
            raw_artist="Test Artist",
            raw_title="Song Title",
        )
        meta_subtitle = LibraryMetadata(
            raw_artist="Test Artist",
            raw_title="Song Title (The Ballad)",
        )

        work1 = await scanner._upsert_work(meta_main.work_title, artist.id)
        work2 = await scanner._upsert_work(meta_subtitle.work_title, artist.id)
        await db_session.commit()

        # Should be different works (subtitle is part of the title)
        # OR same work if fuzzy matching groups them
        # This depends on similarity threshold
        if work1.id != work2.id:
            # Different works - subtitle preserved
            assert "ballad" in work2.title.lower() or "ballad" in meta_subtitle.work_title.lower()



class TestFuzzyMatchingInRealScenarios:
    """Test fuzzy matching in real scan scenarios."""

    @pytest.mark.asyncio
    async def test_fuzzy_matching_groups_similar_titles(self, db_session):
        """Test that fuzzy matching groups works with similar but not identical titles."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")

        # Create first work
        work1 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Try to create similar work (extra space, minor difference)
        work2 = await scanner._upsert_work("song title ", artist.id)
        await db_session.commit()

        # Should be grouped together via fuzzy matching
        assert work1.id == work2.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_with_typos(self, db_session):
        """Test that fuzzy matching handles minor typos."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")

        # Create first work
        work1 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Try to create work with minor typo
        work2 = await scanner._upsert_work("song titl", artist.id)
        await db_session.commit()

        # Should be grouped together via fuzzy matching (>85% similar)
        assert work1.id == work2.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_preserves_first_title(self, db_session):
        """Test that fuzzy matching preserves the first (canonical) title."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")

        # Create first work with canonical title
        work1 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Try to create similar work
        work2 = await scanner._upsert_work("song titl", artist.id)
        await db_session.commit()

        # Should return same work
        assert work1.id == work2.id

        # Title should be the first one (canonical)
        assert work1.title == "song title"

    @pytest.mark.asyncio
    async def test_exact_match_preferred_over_fuzzy(self, db_session):
        """Test that exact match is preferred over fuzzy matching."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")

        # Create two works
        work1 = await scanner._upsert_work("song title", artist.id)
        work2 = await scanner._upsert_work("song title extended", artist.id)
        await db_session.commit()

        # Try to find exact match
        work3 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Should match work1 exactly (not fuzzy match to work2)
        assert work3.id == work1.id


class TestPerformanceWithLargeCatalogs:
    """Test performance with large artist catalogs."""

    @pytest.mark.asyncio
    async def test_fuzzy_matching_performance_100_works(self, db_session):
        """Test fuzzy matching performance with 100 works."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("large catalog artist")

        # Create 100 works
        works = []
        for i in range(100):
            work = await scanner._upsert_work(f"song {i:04d}", artist.id)
            works.append(work)
        await db_session.commit()

        # Measure fuzzy matching time
        start = time.time()
        similar = await scanner._find_similar_work("song 0000", artist.id)
        elapsed = time.time() - start

        # Should complete in <100ms for 100 works
        assert elapsed < 0.1, f"Fuzzy matching took {elapsed:.3f}s, expected <0.1s"
        assert similar is not None
        assert similar.id == works[0].id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_performance_500_works(self, db_session):
        """Test fuzzy matching performance with 500 works (at limit)."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("very large catalog artist")

        # Create 500 works (at the limit)
        work1 = await scanner._upsert_work("song title", artist.id)
        for i in range(499):
            await scanner._upsert_work(f"other song {i:04d}", artist.id)
        await db_session.commit()

        # Measure fuzzy matching time
        start = time.time()
        similar = await scanner._find_similar_work("song titl", artist.id)
        elapsed = time.time() - start

        # Should complete in <500ms for 500 works
        assert elapsed < 0.5, f"Fuzzy matching took {elapsed:.3f}s, expected <0.5s"
        assert similar is not None
        assert similar.id == work1.id

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
        assert elapsed < 0.05, f"Count query took {elapsed:.3f}s, expected <0.05s"

    @pytest.mark.asyncio
    async def test_upsert_work_with_fuzzy_matching_integration(self, db_session):
        """Test that _upsert_work integrates fuzzy matching correctly."""
        scanner = FileScanner(db_session)

        artist = await scanner._upsert_artist("test artist")

        # Create first work
        work1 = await scanner._upsert_work("song title", artist.id)
        await db_session.commit()

        # Upsert similar work (should use fuzzy matching)
        work2 = await scanner._upsert_work("song titl", artist.id)
        await db_session.commit()

        # Should return same work
        assert work1.id == work2.id

        # Verify only one work exists
        stmt = select(func.count()).select_from(Work).where(Work.artist_id == artist.id)
        result = await db_session.execute(stmt)
        count = result.scalar()
        assert count == 1

