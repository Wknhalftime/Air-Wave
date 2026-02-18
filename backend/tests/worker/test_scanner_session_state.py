"""
Test session state management during parallel processing with IntegrityError.

This test verifies the fix for the issue where IntegrityError in one parallel task
would put the session in 'prepared' state, causing all other parallel tasks to fail
with "This session is in 'prepared' state; no further SQL can be emitted within this transaction."
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from airwave.worker.scanner import FileScanner, ScanStats
from airwave.core.models import Artist


@pytest.mark.asyncio
async def test_parallel_processing_with_integrity_error(db_session: AsyncSession, tmp_path: Path):
    """Test that IntegrityError in one file doesn't break parallel processing of other files.

    This reproduces the exact scenario from the logs:
    1. Multiple files are being processed in parallel (up to 10 concurrent)
    2. One file hits a DuplicateIDError (IntegrityError)
    3. SQLAlchemy automatically rolls back the transaction
    4. The session enters 'prepared' state
    5. All other parallel tasks should still be able to continue

    The fix ensures that we explicitly rollback after IntegrityError to clear
    the session state and allow other parallel tasks to continue.
    """
    scanner = FileScanner(db_session)

    # Create 5 fake audio files
    files = []
    for i in range(5):
        test_file = tmp_path / f"test_{i}.flac"
        test_file.write_bytes(b"fake audio data")
        files.append(test_file)

    # Mock process_file to simulate IntegrityError on first file
    call_count = 0
    original_process_file = scanner.process_file

    async def mock_process_file(file_path, stats):
        nonlocal call_count
        call_count += 1

        # First call raises IntegrityError (simulating race condition)
        if call_count == 1:
            # Simulate the error being caught and handled
            error = IntegrityError(
                "UNIQUE constraint failed: album.title, album.artist_id",
                params=None,
                orig=Exception("Test error")
            )
            await scanner._handle_file_error(file_path, error, stats)
        else:
            # Other calls succeed (just update stats)
            stats.created += 1
            stats.processed += 1

    with patch.object(scanner, 'process_file', side_effect=mock_process_file):
        stats = ScanStats()

        # Process files in parallel (simulating real scanner behavior)
        await scanner._process_files_with_semaphore(files, stats, task_id=None)

        # Verify results
        assert stats.processed == 5, f"Expected 5 files processed, got {stats.processed}"
        assert stats.errors == 1, f"Expected 1 error (IntegrityError), got {stats.errors}"
        assert stats.created == 4, f"Expected 4 files created (1 failed), got {stats.created}"

        # CRITICAL: Verify session is still usable after IntegrityError
        # This would fail with "session is in 'prepared' state" before the fix
        result = await db_session.execute(select(Artist))
        artists = result.scalars().all()
        # Session should still be usable
        assert result is not None, "Session should still be usable after IntegrityError"


@pytest.mark.asyncio
async def test_session_state_after_integrity_error(db_session: AsyncSession, tmp_path: Path):
    """Test that session state is properly reset after IntegrityError.
    
    This is a simpler, more focused test that verifies the session rollback logic.
    """
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
            stats = ScanStats()
            
            # This should handle the error and rollback
            await scanner.process_file(test_file, stats)
            
            # Verify error was counted
            assert stats.errors == 1
            
            # CRITICAL: Verify session is still usable (not in 'prepared' state)
            # This would fail before the fix with:
            # "This session is in 'prepared' state; no further SQL can be emitted within this transaction."
            result = await db_session.execute(select(Artist))
            # Should not raise InvalidRequestError
            assert result is not None, "Session should be usable after IntegrityError"


@pytest.mark.asyncio
async def test_multiple_integrity_errors_in_parallel(db_session: AsyncSession, tmp_path: Path):
    """Test that multiple IntegrityErrors in parallel don't break the session.

    This is the worst-case scenario: multiple files hitting IntegrityError simultaneously.
    """
    scanner = FileScanner(db_session)

    # Create 10 fake audio files
    files = []
    for i in range(10):
        test_file = tmp_path / f"test_{i}.flac"
        test_file.write_bytes(b"fake audio data")
        files.append(test_file)

    # Mock process_file to simulate IntegrityError on half the files
    call_count = 0

    async def mock_process_file(file_path, stats):
        nonlocal call_count
        call_count += 1

        # Every other call raises IntegrityError
        if call_count % 2 == 0:
            error = IntegrityError(
                "UNIQUE constraint failed",
                params=None,
                orig=Exception("Test error")
            )
            await scanner._handle_file_error(file_path, error, stats)
        else:
            # Successful calls
            stats.created += 1
            stats.processed += 1

    with patch.object(scanner, 'process_file', side_effect=mock_process_file):
        stats = ScanStats()

        # Process files in parallel
        await scanner._process_files_with_semaphore(files, stats, task_id=None)

        # Verify results
        assert stats.processed == 10, f"Expected 10 files processed, got {stats.processed}"
        assert stats.errors == 5, f"Expected 5 errors (half the files), got {stats.errors}"

        # CRITICAL: Verify session is still usable
        result = await db_session.execute(select(Artist))
        # Should not raise InvalidRequestError
        assert result is not None, "Session should be usable after multiple IntegrityErrors"

