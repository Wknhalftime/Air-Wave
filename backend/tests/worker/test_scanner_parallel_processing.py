"""Tests for scanner parallel file processing.

This module tests the parallel processing implementation with semaphore-limited
concurrency to verify performance improvements and thread safety.
"""

import asyncio
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip if aiosqlite not available
pytest.importorskip("aiosqlite")

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from airwave.core.models import Base
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


@pytest.mark.asyncio
async def test_parallel_processing_enabled_by_default(async_session):
    """Test that parallel processing is enabled by default."""
    scanner = FileScanner(async_session)

    # Default should be 10 concurrent files
    assert scanner.config.max_concurrent_files == 10
    assert hasattr(scanner, '_processing_lock')


@pytest.mark.asyncio
async def test_custom_concurrency_limit(async_session):
    """Test that custom concurrency limit can be set."""
    scanner = FileScanner(async_session, max_concurrent_files=5)

    assert scanner.config.max_concurrent_files == 5


@pytest.mark.asyncio
async def test_parallel_processing_performance(async_session):
    """Test that parallel processing is faster than sequential."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 20 mock audio files
        for i in range(20):
            file_path = Path(tmpdir) / f"song_{i}.mp3"
            file_path.write_bytes(b"fake audio data")
        
        # Mock metadata extraction with 100ms delay to simulate I/O.
        # _extract_metadata is sync and run in executor - use time.sleep, not asyncio.sleep.
        def slow_extract(file_path):
            time.sleep(0.1)  # 100ms delay
            return None

        # Test with parallel processing (10 concurrent)
        scanner_parallel = FileScanner(async_session, max_concurrent_files=10)
        with patch.object(scanner_parallel, '_extract_metadata', side_effect=slow_extract):
            start_time = time.time()
            await scanner_parallel.scan_directory(tmpdir)
            parallel_duration = time.time() - start_time
        
        # With 20 files and 10 concurrent, should take ~200ms (2 batches of 100ms)
        # Allow some overhead, so check < 500ms
        assert parallel_duration < 0.5, f"Parallel processing took {parallel_duration}s, expected < 0.5s"
        
        # Sequential would take 20 * 100ms = 2000ms = 2s
        # So parallel should be at least 3x faster
        expected_sequential_time = 2.0
        speedup = expected_sequential_time / parallel_duration
        assert speedup > 3, f"Speedup was only {speedup}x, expected > 3x"


@pytest.mark.asyncio
async def test_concurrency_limit_respected(async_session):
    """Test that concurrency limit is respected (max N files at once)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 30 files
        for i in range(30):
            file_path = Path(tmpdir) / f"song_{i}.mp3"
            file_path.write_bytes(b"fake audio data")
        
        max_concurrent = 5
        concurrent_count = 0
        max_observed_concurrent = 0
        lock = threading.Lock()

        # _extract_metadata is sync and run in executor - use time.sleep and threading.Lock.
        def track_concurrency(file_path):
            nonlocal concurrent_count, max_observed_concurrent

            with lock:
                concurrent_count += 1
                max_observed_concurrent = max(max_observed_concurrent, concurrent_count)

            time.sleep(0.05)  # Simulate work

            with lock:
                concurrent_count -= 1

            return None

        scanner = FileScanner(async_session, max_concurrent_files=max_concurrent)
        with patch.object(scanner, '_extract_metadata', side_effect=track_concurrency):
            await scanner.scan_directory(tmpdir)
        
        # Should never exceed the concurrency limit
        assert max_observed_concurrent <= max_concurrent, \
            f"Observed {max_observed_concurrent} concurrent, limit was {max_concurrent}"


@pytest.mark.asyncio
async def test_thread_safe_stats_updates(async_session):
    """Test that stats are updated thread-safely during parallel processing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 50 files
        num_files = 50
        for i in range(num_files):
            file_path = Path(tmpdir) / f"song_{i}.mp3"
            file_path.write_bytes(b"fake audio data")
        
        scanner = FileScanner(async_session, max_concurrent_files=10)
        
        # Mock metadata extraction to return None (skip files)
        with patch.object(scanner, '_extract_metadata', return_value=None):
            stats = await scanner.scan_directory(tmpdir)
        
        # All files should be counted exactly once
        assert stats.processed == num_files
        assert stats.skipped == num_files  # All skipped because metadata is None


@pytest.mark.asyncio
async def test_error_handling_in_parallel_processing(async_session):
    """Test that errors in one file don't stop processing of other files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 10 files
        for i in range(10):
            file_path = Path(tmpdir) / f"song_{i}.mp3"
            file_path.write_bytes(b"fake audio data")
        
        call_count = 0

        def failing_extract(file_path):
            nonlocal call_count
            call_count += 1
            # Fail on every other file
            if call_count % 2 == 0:
                raise Exception("Simulated extraction failure")
            return None

        scanner = FileScanner(async_session, max_concurrent_files=5)
        with patch.object(scanner, '_extract_metadata', side_effect=failing_extract):
            stats = await scanner.scan_directory(tmpdir)
        
        # All files should be processed
        assert stats.processed == 10
        # Half should have errors
        assert stats.errors == 5
        # Half should be skipped (metadata is None)
        assert stats.skipped == 5


@pytest.mark.asyncio
async def test_performance_metrics_track_concurrency(async_session):
    """Test that performance metrics track concurrency settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.mp3"
        file_path.write_bytes(b"fake audio data")
        
        max_concurrent = 15
        scanner = FileScanner(async_session, max_concurrent_files=max_concurrent)
        
        with patch.object(scanner, '_extract_metadata', return_value=None):
            await scanner.scan_directory(tmpdir)
        
        # Performance metrics should track the concurrency setting
        assert scanner.perf_metrics.file.max_concurrent_files == max_concurrent


@pytest.mark.asyncio
async def test_directories_processed_metric(async_session):
    """Test that directories processed metric is tracked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested directory structure
        # tmpdir/
        #   subdir1/
        #     song1.mp3
        #   subdir2/
        #     song2.mp3
        subdir1 = Path(tmpdir) / "subdir1"
        subdir2 = Path(tmpdir) / "subdir2"
        subdir1.mkdir()
        subdir2.mkdir()
        
        (subdir1 / "song1.mp3").write_bytes(b"fake audio data")
        (subdir2 / "song2.mp3").write_bytes(b"fake audio data")
        
        scanner = FileScanner(async_session)
        
        with patch.object(scanner, '_extract_metadata', return_value=None):
            await scanner.scan_directory(tmpdir)
        
        # Should have processed 3 directories: tmpdir, subdir1, subdir2
        assert scanner.perf_metrics.file.directories_processed == 3


@pytest.mark.asyncio
async def test_commit_coordination_in_parallel_processing(async_session):
    """Test that commits are coordinated properly during parallel processing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 150 files to trigger multiple commit opportunities
        for i in range(150):
            file_path = Path(tmpdir) / f"song_{i}.mp3"
            file_path.write_bytes(b"fake audio data")
        
        scanner = FileScanner(async_session, max_concurrent_files=10)
        
        with patch.object(scanner, '_extract_metadata', return_value=None):
            stats = await scanner.scan_directory(tmpdir)
        
        # All files should be processed
        assert stats.processed == 150
        
        # Commits should have been tracked
        total_commit_opportunities = (
            scanner.perf_metrics.db.commits_executed + 
            scanner.perf_metrics.db.commits_skipped
        )
        # Should have at least 1 commit opportunity at 100 files
        assert total_commit_opportunities >= 1

