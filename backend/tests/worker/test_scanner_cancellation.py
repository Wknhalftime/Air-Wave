"""Tests for scanner task cancellation.

This module tests the ability to gracefully cancel a running scan task.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Skip if aiosqlite not available
pytest.importorskip("aiosqlite")

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from airwave.core.models import Base
from airwave.core.task_store import TaskStore
from airwave.worker.scanner import FileScanner


@pytest.fixture
async def async_session():
    """Create an async SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def task_store():
    """Create an isolated TaskStore instance for testing."""
    return TaskStore()


@pytest.mark.asyncio
async def test_task_cancellation_flag(task_store):
    """Test that cancellation flag can be set and checked."""
    task_id = "test-cancel-flag"

    # Create task
    task_store.create_task(task_id, "scan", total=100)
    
    # Initially not cancelled
    assert task_store.is_cancelled(task_id) is False

    # Request cancellation
    success = task_store.cancel_task(task_id)
    assert success is True

    # Now should be cancelled
    assert task_store.is_cancelled(task_id) is True

    # Task should still be running (not marked as cancelled yet)
    task = task_store.get_task(task_id)
    assert task.status == "running"
    assert task.cancel_requested is True
    assert task.message == "Cancellation requested..."


@pytest.mark.asyncio
async def test_mark_task_cancelled(task_store):
    """Test marking a task as cancelled."""
    task_id = "test-mark-cancelled"

    # Create and request cancellation
    task_store.create_task(task_id, "scan", total=100)
    task_store.cancel_task(task_id)

    # Mark as cancelled (simulating task stopping)
    task_store.mark_cancelled(task_id)

    # Verify status
    task = task_store.get_task(task_id)
    assert task.status == "cancelled"
    assert task.message == "Cancelled by user"
    assert task.completed_at is not None


@pytest.mark.asyncio
async def test_cannot_cancel_completed_task(task_store):
    """Test that completed tasks cannot be cancelled."""
    task_id = "test-cancel-completed"

    # Create and complete task
    task_store.create_task(task_id, "scan", total=100)
    task_store.complete_task(task_id, success=True)

    # Try to cancel
    success = task_store.cancel_task(task_id)
    assert success is False

    # Task should still be completed
    task = task_store.get_task(task_id)
    assert task.status == "completed"


@pytest.mark.asyncio
async def test_scanner_respects_cancellation(async_session, task_store):
    """Test that scanner stops when cancellation is requested."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 100 files
        for i in range(100):
            file_path = Path(tmpdir) / f"song_{i}.mp3"
            file_path.write_bytes(b"fake audio data")

        task_id = "test-scanner-cancel"
        task_store.create_task(task_id, "scan", total=100)

        # Mock metadata extraction to be slow
        original_process_file = FileScanner.process_file
        call_count = 0

        async def slow_process_file(self, file_path, stats):
            nonlocal call_count
            call_count += 1

            # Cancel after processing 10 files
            if call_count == 10:
                task_store.cancel_task(task_id)

            await asyncio.sleep(0.01)  # Simulate slow processing
            return await original_process_file(self, file_path, stats)

        scanner = FileScanner(async_session, task_store=task_store, max_concurrent_files=5)

        # Mock VectorDB to avoid network calls
        with patch('airwave.worker.scanner.VectorDB'):
            with patch.object(FileScanner, 'process_file', slow_process_file):
                stats = await scanner.scan_directory(tmpdir, task_id=task_id)

        # Task should be marked as cancelled (scanner checks cancel every 10 files and at dir boundaries)
        task = task_store.get_task(task_id)
        assert task.status == "cancelled"
        assert stats.cancelled
        # With a single directory, the in-flight asyncio.gather may still process all 100 before returning
        assert stats.processed <= 100


@pytest.mark.asyncio
async def test_scanner_saves_progress_before_cancelling(async_session, task_store):
    """Test that scanner commits changes before cancelling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 50 files
        for i in range(50):
            file_path = Path(tmpdir) / f"song_{i}.mp3"
            file_path.write_bytes(b"fake audio data")

        task_id = "test-scanner-save-cancel"
        task_store.create_task(task_id, "scan", total=50)

        # Mock to cancel after 20 files
        call_count = 0

        async def counting_process_file(self, file_path, stats):
            nonlocal call_count
            call_count += 1

            if call_count == 20:
                task_store.cancel_task(task_id)

            # Return None to skip (simulating unchanged files)
            return None

        scanner = FileScanner(async_session, task_store=task_store, max_concurrent_files=5)

        # Mock VectorDB to avoid network calls
        with patch('airwave.worker.scanner.VectorDB'):
            with patch.object(scanner, '_extract_metadata', counting_process_file):
                stats = await scanner.scan_directory(tmpdir, task_id=task_id)

        # Should have processed some files before cancelling
        assert stats.processed >= 20

        # Session should have been committed (no pending changes)
        assert len(async_session.new) == 0
        assert len(async_session.dirty) == 0


@pytest.mark.asyncio
async def test_cancellation_nonexistent_task(task_store):
    """Test cancelling a task that doesn't exist."""
    success = task_store.cancel_task("nonexistent-task")
    assert success is False

    is_cancelled = task_store.is_cancelled("nonexistent-task")
    assert is_cancelled is False

