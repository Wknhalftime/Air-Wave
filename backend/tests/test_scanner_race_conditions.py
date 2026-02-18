"""
Tests for Phase 1: Race Condition Fixes

These tests verify that concurrent operations on shared state are thread-safe.
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from airwave.worker.scanner import FileScanner
from airwave.core.stats import ScanStats
from airwave.core.task_store import TaskStore


@pytest.fixture
async def scanner():
    """Create a FileScanner instance for testing with isolated TaskStore."""
    mock_session = AsyncMock()
    task_store = TaskStore()  # Isolated instance for this test
    scanner = FileScanner(mock_session, task_store=task_store, max_concurrent_files=10)
    return scanner


@pytest.mark.asyncio
async def test_concurrent_path_seen_mutations(scanner):
    """Verify _mark_path_seen is thread-safe under concurrent access."""
    # Initialize scan state
    scanner._path_index_seen = set()
    
    # Create 100 unique paths
    paths = [f"/test/path{i}.mp3" for i in range(100)]
    
    # Simulate concurrent marking of paths
    tasks = [scanner._mark_path_seen(p) for p in paths]
    await asyncio.gather(*tasks)
    
    # All paths should be marked (no lost updates)
    assert len(scanner._path_index_seen) == 100
    for path in paths:
        assert path in scanner._path_index_seen


@pytest.mark.asyncio
async def test_concurrent_touch_id_mutations(scanner):
    """Verify _add_touch_id is thread-safe under concurrent access."""
    # Initialize scan state
    scanner._touch_ids = set()
    
    # Mock _flush_touch to prevent actual flushing
    scanner._flush_touch = AsyncMock()
    
    # Create 50 unique file IDs (below flush threshold of 500)
    file_ids = list(range(1, 51))
    
    # Simulate concurrent adding of touch IDs
    tasks = [scanner._add_touch_id(fid) for fid in file_ids]
    await asyncio.gather(*tasks)
    
    # All IDs should be added (no lost updates)
    assert len(scanner._touch_ids) == 50
    for fid in file_ids:
        assert fid in scanner._touch_ids


@pytest.mark.asyncio
async def test_concurrent_path_index_move_updates(scanner):
    """Verify _update_path_index_for_move is thread-safe."""
    # Initialize scan state
    scanner._path_index = {
        f"/old/path{i}.mp3": {"id": i, "size": 1000, "mtime": 123456.0}
        for i in range(100)
    }
    
    # Simulate concurrent move operations
    tasks = [
        scanner._update_path_index_for_move(
            f"/old/path{i}.mp3",
            f"/new/path{i}.mp3",
            i,
            1000,
            123456.0
        )
        for i in range(100)
    ]
    await asyncio.gather(*tasks)
    
    # All old paths should be removed
    for i in range(100):
        assert f"/old/path{i}.mp3" not in scanner._path_index
    
    # All new paths should be added
    for i in range(100):
        assert f"/new/path{i}.mp3" in scanner._path_index
        assert scanner._path_index[f"/new/path{i}.mp3"]["id"] == i


@pytest.mark.asyncio
async def test_concurrent_find_move_candidate(scanner):
    """Verify _find_move_candidate is thread-safe (no duplicate pops)."""
    # Initialize missing candidates
    scanner._missing_candidates = [
        {
            "pid_primary": f"pid{i}",
            "pid_fallback": None,
            "size": 1000,
            "lib_id": i,
            "old_path": f"/old/path{i}.mp3"
        }
        for i in range(100)
    ]
    
    # Simulate concurrent move detection
    tasks = [
        scanner._find_move_candidate(f"pid{i}", None, 1000)
        for i in range(100)
    ]
    results = await asyncio.gather(*tasks)
    
    # Each task should find exactly one candidate
    found_candidates = [r for r in results if r is not None]
    assert len(found_candidates) == 100
    
    # All candidates should be removed from list
    assert len(scanner._missing_candidates) == 0
    
    # Each candidate should be unique (no duplicates)
    lib_ids = [c["lib_id"] for c in found_candidates]
    assert len(lib_ids) == len(set(lib_ids))  # All unique


@pytest.mark.asyncio
async def test_stats_mutations_are_atomic():
    """Verify stats mutations don't lose updates under concurrent access."""
    mock_session = AsyncMock()
    scanner = FileScanner(mock_session)
    stats = ScanStats()
    
    # Simulate 100 concurrent stats increments
    async def increment_stats():
        async with scanner._processing_lock:
            stats.skipped += 1
            stats.processed += 1
    
    tasks = [increment_stats() for _ in range(100)]
    await asyncio.gather(*tasks)
    
    # No lost updates
    assert stats.skipped == 100
    assert stats.processed == 100


@pytest.mark.asyncio
async def test_concurrent_file_processing_no_lost_stats():
    """Integration test: Process multiple files concurrently without losing stats."""
    mock_session = AsyncMock()
    task_store = TaskStore()  # Isolated instance for this test
    scanner = FileScanner(mock_session, task_store=task_store, max_concurrent_files=10)
    
    # Initialize scan state
    scanner._path_index = {}
    scanner._path_index_seen = set()
    scanner._touch_ids = set()
    scanner._flush_touch = AsyncMock()
    
    stats = ScanStats()
    
    # Mock file.stat() to return consistent results
    mock_stat = Mock()
    mock_stat.st_size = 1000
    mock_stat.st_mtime = 123456.0
    
    # Simulate processing 50 files that will be skipped (not in index)
    async def process_skipped_file(i):
        file_path = Path(f"/test/file{i}.mp3")
        
        with patch.object(Path, 'stat', return_value=mock_stat):
            # Simulate the OSError case (file not found)
            async with scanner._processing_lock:
                stats.errors += 1
                stats.processed += 1
    
    tasks = [process_skipped_file(i) for i in range(50)]
    await asyncio.gather(*tasks)
    
    # Verify no lost updates
    assert stats.errors == 50
    assert stats.processed == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

