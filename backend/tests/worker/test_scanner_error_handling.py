"""
Tests for scanner database error handling and race condition recovery.

Tests verify that the scanner can handle:
- UNIQUE constraint violations from parallel processing
- Database errors without crashing the entire scan
- Session rollback and recovery
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.worker.scanner import FileScanner
from airwave.core.models import Artist, Album, Work, Recording


class TestDatabaseErrorHandling:
    """Test database error handling and recovery."""

    @pytest.mark.asyncio
    async def test_album_creation_race_condition(self, db_session: AsyncSession):
        """Test that album creation handles UNIQUE constraint violations gracefully."""
        # Create artist
        artist = Artist(name="test artist")
        db_session.add(artist)
        await db_session.flush()

        scanner = FileScanner(db_session)

        # First call should create the album
        album1 = await scanner._get_or_create_album("test album", artist.id)
        assert album1.title == "test album"
        assert album1.artist_id == artist.id
        await db_session.commit()

        # Second call should return the existing album (not create duplicate)
        album2 = await scanner._get_or_create_album("test album", artist.id)
        assert album2.id == album1.id
        assert album2.title == "test album"

    @pytest.mark.asyncio
    async def test_recording_creation_race_condition(self, db_session: AsyncSession):
        """Test that recording UPSERT handles race conditions gracefully."""
        # Create hierarchy
        artist = Artist(name="test artist")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="test work", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        scanner = FileScanner(db_session)

        # First call should create the recording
        rec1 = await scanner._upsert_recording(
            work.id, "test recording", "Original", duration=180.0
        )
        assert rec1.title == "test recording"
        assert rec1.work_id == work.id
        await db_session.commit()

        # Second call should return the existing recording (UPSERT is idempotent)
        rec2 = await scanner._upsert_recording(
            work.id, "test recording", "Original", duration=180.0
        )
        assert rec2.id == rec1.id
        assert rec2.title == "test recording"

    @pytest.mark.asyncio
    async def test_album_creation_with_flush_error(self, db_session: AsyncSession):
        """Test that album creation handles flush errors with rollback and retry."""
        # Create artist
        artist = Artist(name="test artist")
        db_session.add(artist)
        await db_session.flush()

        scanner = FileScanner(db_session)

        # Create the album first
        album = Album(title="existing album", artist_id=artist.id)
        db_session.add(album)
        await db_session.flush()
        await db_session.commit()

        # Mock flush to raise IntegrityError on first call, then succeed
        original_flush = db_session.flush
        flush_call_count = 0

        async def mock_flush():
            nonlocal flush_call_count
            flush_call_count += 1
            if flush_call_count == 1:
                # Simulate UNIQUE constraint error
                raise IntegrityError(
                    "UNIQUE constraint failed: albums.id",
                    params=None,
                    orig=Exception("UNIQUE constraint failed")
                )
            return await original_flush()

        with patch.object(db_session, 'flush', side_effect=mock_flush):
            # This should handle the error and return the existing album
            result = await scanner._get_or_create_album("existing album", artist.id)
            assert result.id == album.id
            assert result.title == "existing album"

    @pytest.mark.asyncio
    async def test_process_file_error_recovery(self, db_session: AsyncSession, tmp_path: Path):
        """Test that process_file handles errors without crashing the scan."""
        scanner = FileScanner(db_session)

        # Create a fake audio file
        test_file = tmp_path / "test.flac"
        test_file.write_bytes(b"fake audio data")

        # Mock _extract_metadata to raise an error
        with patch.object(scanner, '_extract_metadata', side_effect=Exception("Test error")):
            # Create stats object
            from airwave.worker.scanner import ScanStats
            stats = ScanStats()

            # This should NOT crash, just increment error counter
            await scanner.process_file(test_file, stats)

            # Verify error was counted
            assert stats.errors == 1
            assert stats.created == 0

    @pytest.mark.asyncio
    async def test_multiple_errors_dont_crash_scan(self, db_session: AsyncSession, tmp_path: Path):
        """Test that multiple errors in a row don't crash the scan."""
        scanner = FileScanner(db_session)

        # Create multiple fake files
        files = []
        for i in range(5):
            test_file = tmp_path / f"test{i}.flac"
            test_file.write_bytes(b"fake audio data")
            files.append(test_file)

        # Mock _extract_metadata to raise errors for all files
        with patch.object(scanner, '_extract_metadata', side_effect=Exception("Test error")):
            from airwave.worker.scanner import ScanStats
            stats = ScanStats()

            # Process all files - none should crash
            for file in files:
                await scanner.process_file(file, stats)

            # All should be counted as errors
            assert stats.errors == 5
            assert stats.created == 0

    @pytest.mark.asyncio
    async def test_session_rollback_on_error(self, db_session: AsyncSession, tmp_path: Path):
        """Test that session is properly rolled back after database errors."""
        scanner = FileScanner(db_session)

        # Create a fake audio file
        test_file = tmp_path / "test.flac"
        test_file.write_bytes(b"fake audio data")

        # Mock _get_or_create_album to raise IntegrityError
        async def mock_create_album(*args, **kwargs):
            raise IntegrityError(
                "UNIQUE constraint failed",
                params=None,
                orig=Exception("Test error")
            )

        with patch.object(scanner, '_get_or_create_album', side_effect=mock_create_album):
            with patch.object(scanner, '_extract_metadata', return_value=MagicMock()):
                from airwave.worker.scanner import ScanStats
                stats = ScanStats()

                # This should handle the error and rollback
                await scanner.process_file(test_file, stats)

                # Verify error was counted
                assert stats.errors == 1

                # Verify session is still usable (not in rolled-back state)
                # Try a simple query
                from airwave.core.models import Artist
                from sqlalchemy import select
                result = await db_session.execute(select(Artist))
                # Should not raise "transaction has been rolled back" error

