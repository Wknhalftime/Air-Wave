"""Comprehensive tests for the Matcher module.

This test suite covers:
- Batch matching with deduplication
- Identity Bridge matching
- Exact match strategy
- Variant match strategy (fuzzy matching)
- Vector semantic search
- Alias match threshold
- Match explain mode
- scan_and_promote functionality
- link_orphaned_logs functionality
"""

import shutil
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from airwave.core.models import (
    Artist,
    BroadcastLog,
    IdentityBridge,
    Recording,
    Station,
    Work,
)
from airwave.core.normalization import Normalizer
from airwave.core.vector_db import VectorDB
from airwave.worker.matcher import Matcher
from sqlalchemy import select


class TestMatcherBatchProcessing:
    """Test batch matching and deduplication."""

    @pytest.mark.asyncio
    async def test_match_batch_deduplication(self, db_session):
        """Test that match_batch deduplicates identical queries."""
        # Create test data
        artist = Artist(name="test artist")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="test song", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        recording = Recording(
            work_id=work.id, title="test song", version_type="Original"
        )
        db_session.add(recording)
        await db_session.commit()

        matcher = Matcher(db_session)
        matcher._vector_db = MagicMock()
        matcher._vector_db.search_batch.return_value = [[(recording.id, 0.05)]]

        # Submit duplicate queries
        queries = [
            ("Test Artist", "Test Song"),
            ("Test Artist", "Test Song"),  # Duplicate
            ("Test Artist", "Test Song"),  # Duplicate
        ]

        results = await matcher.match_batch(queries)

        # Should only process once but return results for all queries
        assert len(results) == 1  # Deduplicated
        assert ("Test Artist", "Test Song") in results

    @pytest.mark.asyncio
    async def test_match_batch_empty_queries(self, db_session):
        """Test match_batch handles empty query list."""
        matcher = Matcher(db_session)
        results = await matcher.match_batch([])
        assert results == {}


class TestIdentityBridgeMatching:
    """Test Identity Bridge matching strategy."""

    @pytest.mark.asyncio
    async def test_identity_bridge_exact_match(self, db_session):
        """Test that Identity Bridge provides instant matches."""
        # Create recording
        artist = Artist(name="guns n roses")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="sweet child o mine", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        recording = Recording(
            work_id=work.id, title="sweet child o mine", version_type="Original"
        )
        db_session.add(recording)
        await db_session.flush()

        # Create Identity Bridge
        sig = Normalizer.generate_signature("GnR", "Sweet Child")
        bridge = IdentityBridge(
            log_signature=sig,
            reference_artist="GnR",
            reference_title="Sweet Child",
            recording_id=recording.id,
        )
        db_session.add(bridge)
        await db_session.commit()

        matcher = Matcher(db_session)
        results = await matcher.match_batch([("GnR", "Sweet Child")])

        assert ("GnR", "Sweet Child") in results
        match_id, reason = results[("GnR", "Sweet Child")]
        assert match_id == recording.id
        assert "Identity Bridge" in reason

    @pytest.mark.asyncio
    async def test_identity_bridge_multiple_queries(self, db_session):
        """Test Identity Bridge handles multiple queries efficiently."""
        # Create two recordings with bridges
        artist = Artist(name="metallica")
        db_session.add(artist)
        await db_session.flush()

        work1 = Work(title="enter sandman", artist_id=artist.id)
        work2 = Work(title="nothing else matters", artist_id=artist.id)
        db_session.add_all([work1, work2])
        await db_session.flush()

        rec1 = Recording(
            work_id=work1.id, title="enter sandman", version_type="Original"
        )
        rec2 = Recording(
            work_id=work2.id, title="nothing else matters", version_type="Original"
        )
        db_session.add_all([rec1, rec2])
        await db_session.flush()

        # Create bridges
        sig1 = Normalizer.generate_signature("Metallica", "Sandman")
        sig2 = Normalizer.generate_signature("Metallica", "Nothing Else")

        bridge1 = IdentityBridge(
            log_signature=sig1,
            reference_artist="Metallica",
            reference_title="Sandman",
            recording_id=rec1.id,
        )
        bridge2 = IdentityBridge(
            log_signature=sig2,
            reference_artist="Metallica",
            reference_title="Nothing Else",
            recording_id=rec2.id,
        )
        db_session.add_all([bridge1, bridge2])
        await db_session.commit()

        matcher = Matcher(db_session)
        results = await matcher.match_batch(
            [("Metallica", "Sandman"), ("Metallica", "Nothing Else")]
        )

        assert len(results) == 2
        assert results[("Metallica", "Sandman")][0] == rec1.id
        assert results[("Metallica", "Nothing Else")][0] == rec2.id


class TestVectorSemanticSearch:
    """Test vector semantic search matching."""

    @pytest.mark.asyncio
    async def test_vector_search_fallback(self, db_session):
        """Test that vector search is used when exact match fails."""
        # Create recording
        artist = Artist(name="pink floyd")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="comfortably numb", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        recording = Recording(
            work_id=work.id, title="comfortably numb", version_type="Original"
        )
        db_session.add(recording)
        await db_session.commit()

        matcher = Matcher(db_session)

        # Create temp VectorDB
        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)
            vdb.add_track(recording.id, "pink floyd", "comfortably numb")
            matcher._vector_db = vdb

            # Query with slight variation (should use vector search)
            results = await matcher.match_batch([("Pink Floyd", "Comfortably Numb")])

            assert ("Pink Floyd", "Comfortably Numb") in results
            match_id, reason = results[("Pink Floyd", "Comfortably Numb")]
            assert match_id == recording.id
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_vector_search_with_title_guard(self, db_session):
        """Test that vector search rejects matches with low title similarity."""
        # Create recording
        artist = Artist(name="the beatles")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="hey jude", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        recording = Recording(
            work_id=work.id, title="hey jude", version_type="Original"
        )
        db_session.add(recording)
        await db_session.commit()

        matcher = Matcher(db_session)
        matcher._vector_db = MagicMock()

        # Mock vector search returning a match with low distance
        # but the title is completely different
        matcher._vector_db.search_batch.return_value = [[(recording.id, 0.05)]]

        # Query with same artist but very different title
        results = await matcher.match_batch([("The Beatles", "Let It Be")])

        # Should reject due to title guard (title similarity < 0.5)
        # The query should be in results (even if no match found)
        assert ("The Beatles", "Let It Be") in results
        match_id, reason = results[("The Beatles", "Let It Be")]
        assert match_id is None
        assert reason == "No Match Found"


class TestMatchExplainMode:
    """Test match explain mode for diagnostics."""

    @pytest.mark.asyncio
    async def test_explain_mode_returns_candidates(self, db_session):
        """Test that explain mode returns candidate matches."""
        # Create recording
        artist = Artist(name="radiohead")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="creep", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        recording = Recording(
            work_id=work.id, title="creep", version_type="Original"
        )
        db_session.add(recording)
        await db_session.commit()

        matcher = Matcher(db_session)

        # Create temp VectorDB
        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)
            vdb.add_track(recording.id, "radiohead", "creep")
            matcher._vector_db = vdb

            # Query with explain=True
            results = await matcher.match_batch([("Radiohead", "Creep")], explain=True)

            assert ("Radiohead", "Creep") in results
            result = results[("Radiohead", "Creep")]

            # Explain mode returns dict with match and candidates
            assert isinstance(result, dict)
            assert "match" in result
            assert "candidates" in result
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestScanAndPromote:
    """Test scan_and_promote functionality."""

    @pytest.mark.asyncio
    async def test_scan_and_promote_creates_library(self, db_session):
        """Test that scan_and_promote creates library from unique logs."""
        # Create station
        station = Station(callsign="TEST", frequency="100.0", city="Test City")
        db_session.add(station)
        await db_session.flush()

        # Create unique broadcast logs
        log1 = BroadcastLog(
            station_id=station.id,
            raw_artist="Nirvana",
            raw_title="Smells Like Teen Spirit",
            played_at=datetime.fromisoformat("2024-01-01T10:00:00"),
        )
        log2 = BroadcastLog(
            station_id=station.id,
            raw_artist="Pearl Jam",
            raw_title="Alive",
            played_at=datetime.fromisoformat("2024-01-01T11:00:00"),
        )
        db_session.add_all([log1, log2])
        await db_session.commit()

        matcher = Matcher(db_session)

        # Run scan_and_promote (returns int count)
        created_count = await matcher.scan_and_promote()

        # Verify recordings were created
        stmt = select(Recording)
        res = await db_session.execute(stmt)
        recordings = res.scalars().all()

        assert len(recordings) >= 2
        assert created_count >= 2

    @pytest.mark.asyncio
    async def test_scan_and_promote_deduplicates_signatures(
        self, db_session
    ):
        """Test that scan_and_promote handles duplicate signatures.

        Multiple raw inputs can normalize to the same signature
        (e.g., "GODSMACK" and "Godsmack" both normalize to "godsmack").
        This test ensures only ONE IdentityBridge is created per signature.
        """
        # Create station
        station = Station(callsign="TEST", frequency="100.0", city="Test")
        db_session.add(station)
        await db_session.flush()

        # Create logs with different raw inputs that normalize to same sig
        log1 = BroadcastLog(
            station_id=station.id,
            raw_artist="GODSMACK",  # All caps
            raw_title="I Stand Alone",
            played_at=datetime.fromisoformat("2024-01-01T10:00:00"),
        )
        log2 = BroadcastLog(
            station_id=station.id,
            raw_artist="Godsmack",  # Title case
            raw_title="I Stand Alone",
            played_at=datetime.fromisoformat("2024-01-01T11:00:00"),
        )
        log3 = BroadcastLog(
            station_id=station.id,
            raw_artist="godsmack",  # Lower case
            raw_title="i stand alone",  # Lower case title too
            played_at=datetime.fromisoformat("2024-01-01T12:00:00"),
        )
        db_session.add_all([log1, log2, log3])
        await db_session.commit()

        # Count existing recordings and bridges before promotion
        stmt = select(Recording)
        res = await db_session.execute(stmt)
        recordings_before = len(res.scalars().all())

        stmt = select(IdentityBridge)
        res = await db_session.execute(stmt)
        bridges_before = len(res.scalars().all())

        matcher = Matcher(db_session)

        # Run scan_and_promote
        created_count = await matcher.scan_and_promote()

        # Verify only ONE NEW recording was created (not 3)
        stmt = select(Recording)
        res = await db_session.execute(stmt)
        recordings_after = len(res.scalars().all())
        new_recordings = recordings_after - recordings_before
        assert new_recordings == 1, (
            f"Expected 1 new recording, got {new_recordings}"
        )
        assert created_count == 1

        # Verify only ONE NEW IdentityBridge was created
        stmt = select(IdentityBridge)
        res = await db_session.execute(stmt)
        bridges_after = len(res.scalars().all())
        new_bridges = bridges_after - bridges_before
        assert new_bridges == 1, (
            f"Expected 1 new bridge, got {new_bridges}"
        )

        # Verify the bridge has the correct signature
        stmt = select(IdentityBridge).order_by(
            IdentityBridge.id.desc()
        ).limit(1)
        res = await db_session.execute(stmt)
        bridge = res.scalar_one()

        from airwave.core.normalization import Normalizer

        expected_sig = Normalizer.generate_signature(
            "GODSMACK", "I Stand Alone"
        )
        assert bridge.log_signature == expected_sig

        # Verify the reference preserves one of the raw inputs
        assert bridge.reference_artist in [
            "GODSMACK",
            "Godsmack",
            "godsmack",
        ]
        assert bridge.reference_title in [
            "I Stand Alone",
            "i stand alone",
        ]


class TestLinkOrphanedLogs:
    """Test link_orphaned_logs functionality."""

    @pytest.mark.asyncio
    async def test_link_orphaned_logs_via_bridge(self, db_session):
        """Test that orphaned logs are linked via identity bridges."""
        # Create station
        station = Station(callsign="TEST", frequency="100.0", city="Test City")
        db_session.add(station)
        await db_session.flush()

        # Create recording
        artist = Artist(name="foo fighters")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="everlong", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        recording = Recording(
            work_id=work.id, title="everlong", version_type="Original"
        )
        db_session.add(recording)
        await db_session.flush()

        # Create orphaned log
        log = BroadcastLog(
            station_id=station.id,
            raw_artist="Foo Fighters",
            raw_title="Everlong",
            played_at=datetime.fromisoformat("2024-01-01T10:00:00"),
            recording_id=None,  # Orphaned
        )
        db_session.add(log)
        await db_session.flush()

        # Create identity bridge
        sig = Normalizer.generate_signature("Foo Fighters", "Everlong")
        bridge = IdentityBridge(
            log_signature=sig,
            reference_artist="Foo Fighters",
            reference_title="Everlong",
            recording_id=recording.id,
        )
        db_session.add(bridge)
        await db_session.commit()

        matcher = Matcher(db_session)

        # Run link_orphaned_logs (returns int count)
        linked_count = await matcher.link_orphaned_logs()

        # Verify log was linked
        await db_session.refresh(log)
        assert log.recording_id == recording.id
        assert linked_count >= 1

