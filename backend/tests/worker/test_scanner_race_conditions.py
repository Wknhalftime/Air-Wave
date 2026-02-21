"""
Tests for Phase 1: Race Condition Fixes

These tests verify that concurrent operations on shared state are thread-safe.
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from airwave.core.stats import ScanStats
from airwave.core.task_store import TaskStore
from airwave.worker.scanner import FileScanner


@pytest.fixture
async def scanner():
    """Create a FileScanner instance for testing with isolated TaskStore."""
    mock_session = AsyncMock()
    task_store = TaskStore()
    return FileScanner(
        mock_session, task_store=task_store, max_concurrent_files=10
    )


@pytest.mark.asyncio
async def test_concurrent_path_seen_mutations(scanner):
    """Verify _mark_path_seen is thread-safe under concurrent access."""
    scanner._path_index_seen = set()
    paths = [f"/test/path{i}.mp3" for i in range(100)]

    tasks = [scanner._mark_path_seen(p) for p in paths]
    await asyncio.gather(*tasks)

    assert len(scanner._path_index_seen) == 100
    for path in paths:
        assert path in scanner._path_index_seen


@pytest.mark.asyncio
async def test_concurrent_touch_id_mutations(scanner):
    """Verify _add_touch_id is thread-safe under concurrent access."""
    scanner._touch_ids = set()
    scanner._flush_touch = AsyncMock()

    file_ids = list(range(1, 51))
    tasks = [scanner._add_touch_id(fid) for fid in file_ids]
    await asyncio.gather(*tasks)

    assert len(scanner._touch_ids) == 50
    for fid in file_ids:
        assert fid in scanner._touch_ids


@pytest.mark.asyncio
async def test_concurrent_path_index_move_updates(scanner):
    """Verify _update_path_index_for_move is thread-safe."""
    scanner._path_index = {
        f"/old/path{i}.mp3": {"id": i, "size": 1000, "mtime": 123456.0}
        for i in range(100)
    }

    tasks = [
        scanner._update_path_index_for_move(
            f"/old/path{i}.mp3", f"/new/path{i}.mp3", i, 1000, 123456.0
        )
        for i in range(100)
    ]
    await asyncio.gather(*tasks)

    for i in range(100):
        assert f"/old/path{i}.mp3" not in scanner._path_index
        assert f"/new/path{i}.mp3" in scanner._path_index
        assert scanner._path_index[f"/new/path{i}.mp3"]["id"] == i


@pytest.mark.asyncio
async def test_concurrent_find_move_candidate(scanner):
    """Verify _find_move_candidate is thread-safe (no duplicate pops)."""
    scanner._missing_candidates = [
        {
            "pid_primary": f"pid{i}",
            "pid_fallback": None,
            "size": 1000,
            "lib_id": i,
            "old_path": f"/old/path{i}.mp3",
        }
        for i in range(100)
    ]

    tasks = [
        scanner._find_move_candidate(f"pid{i}", None, 1000) for i in range(100)
    ]
    results = await asyncio.gather(*tasks)

    found_candidates = [r for r in results if r is not None]
    assert len(found_candidates) == 100
    assert len(scanner._missing_candidates) == 0

    lib_ids = [c["lib_id"] for c in found_candidates]
    assert len(lib_ids) == len(set(lib_ids))


@pytest.mark.asyncio
async def test_stats_mutations_are_atomic():
    """Verify stats mutations do not lose updates under concurrent access."""
    mock_session = AsyncMock()
    scanner = FileScanner(mock_session)
    stats = ScanStats()

    async def increment_stats():
        async with scanner._processing_lock:
            stats.skipped += 1
            stats.processed += 1

    tasks = [increment_stats() for _ in range(100)]
    await asyncio.gather(*tasks)

    assert stats.skipped == 100
    assert stats.processed == 100


@pytest.mark.asyncio
async def test_concurrent_file_processing_no_lost_stats():
    """Integration test: Process multiple files concurrently without losing stats."""
    mock_session = AsyncMock()
    task_store = TaskStore()
    scanner = FileScanner(
        mock_session, task_store=task_store, max_concurrent_files=10
    )

    scanner._path_index = {}
    scanner._path_index_seen = set()
    scanner._touch_ids = set()
    scanner._flush_touch = AsyncMock()

    stats = ScanStats()

    mock_stat = Mock()
    mock_stat.st_size = 1000
    mock_stat.st_mtime = 123456.0

    async def process_skipped_file(i):
        file_path = Path(f"/test/file{i}.mp3")
        with patch.object(Path, "stat", return_value=mock_stat):
            async with scanner._processing_lock:
                stats.errors += 1
                stats.processed += 1

    tasks = [process_skipped_file(i) for i in range(50)]
    await asyncio.gather(*tasks)

    assert stats.errors == 50
    assert stats.processed == 50
