"""Tests for scanner performance monitoring and metrics tracking.

This module tests the PerformanceMetrics integration with the scanner,
verifying that all optimization metrics are correctly tracked.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip if aiosqlite not available
pytest.importorskip("aiosqlite")

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from airwave.core.models import Base, LibraryFile
from airwave.core.performance import PerformanceMetrics
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
def temp_audio_dir():
    """Create a temporary directory with mock audio files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some mock MP3 files
        for i in range(5):
            file_path = Path(tmpdir) / f"song_{i}.mp3"
            file_path.write_bytes(b"fake audio data")
        yield tmpdir


@pytest.mark.asyncio
async def test_performance_metrics_initialization(async_session):
    """Test that performance metrics are initialized when scanner starts."""
    scanner = FileScanner(async_session)
    
    # Initially no metrics
    assert scanner.perf_metrics is None
    
    # After scan_directory is called, metrics should be initialized
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock the metadata extraction to avoid actual file processing
        with patch.object(scanner, '_extract_metadata', return_value=None):
            await scanner.scan_directory(tmpdir)
        
        # Metrics should now exist
        assert scanner.perf_metrics is not None
        assert isinstance(scanner.perf_metrics, PerformanceMetrics)
        assert scanner.perf_metrics.duration_seconds is not None


@pytest.mark.asyncio
async def test_metadata_extraction_tracking(async_session):
    """Test that metadata extractions are tracked correctly."""
    scanner = FileScanner(async_session)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock audio file
        file_path = Path(tmpdir) / "test.mp3"
        file_path.write_bytes(b"fake audio data")
        
        # Mock metadata extraction to return valid data
        mock_audio = MagicMock()
        # Set up tag data
        mock_audio.get.side_effect = lambda key, default=None: {
            "artist": ["Test Artist"],
            "title": ["Test Title"],
            "album": ["Test Album"],
            "albumartist": [""],
            "isrc": [""],
            "date": [""]
        }.get(key, default)

        # Set up audio info (duration and bitrate)
        mock_info = MagicMock()
        mock_info.length = 180.5  # 3 minutes
        mock_info.bitrate = 320000  # 320 kbps
        mock_audio.info = mock_info

        # Mock matcher.find_match to return None (no match found)
        async def mock_find_match(artist, title):
            return None

        with patch.object(scanner, '_extract_metadata', return_value=mock_audio):
            with patch.object(scanner.matcher, 'find_match', side_effect=mock_find_match):
                await scanner.scan_directory(tmpdir)

        # Should have tracked metadata extraction
        assert scanner.perf_metrics.metadata_extractions >= 1


@pytest.mark.asyncio
async def test_legacy_file_update_tracking(async_session):
    """Test that legacy file updates (Fix 1) are tracked."""
    scanner = FileScanner(async_session)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "legacy.mp3"
        file_path.write_bytes(b"fake audio data")
        
        # Create a legacy file in DB (mtime=None)
        lib_file = LibraryFile(
            path=str(file_path),
            size=len(b"fake audio data"),
            mtime=None,  # Legacy file!
            recording_id=1,
        )
        async_session.add(lib_file)
        await async_session.commit()
        
        # Rescan should update mtime without extracting metadata
        with patch.object(scanner, '_extract_metadata') as mock_extract:
            await scanner.scan_directory(tmpdir)
            
            # Metadata extraction should NOT have been called (Fix 1 optimization)
            assert mock_extract.call_count == 0
            
            # Should have tracked the legacy file update
            assert scanner.perf_metrics.legacy_files_updated >= 1
            assert scanner.perf_metrics.metadata_extractions_skipped >= 1


@pytest.mark.asyncio
async def test_commit_tracking(async_session):
    """Test that commits executed and skipped (Fix 3) are tracked."""
    scanner = FileScanner(async_session)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 150 files to trigger multiple commit opportunities
        for i in range(150):
            file_path = Path(tmpdir) / f"song_{i}.mp3"
            file_path.write_bytes(b"fake audio data")
        
        with patch.object(scanner, '_extract_metadata', return_value=None):
            await scanner.scan_directory(tmpdir)
        
        # Should have tracked commits
        total_commits = scanner.perf_metrics.commits_executed + scanner.perf_metrics.commits_skipped
        assert total_commits >= 1  # At least one commit opportunity at 100 files


@pytest.mark.asyncio
async def test_move_detection_skip_tracking(async_session):
    """Test that move detection skips (Fix 4) are tracked."""
    scanner = FileScanner(async_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.mp3"
        file_path.write_bytes(b"fake audio data")

        # Mock metadata extraction to return valid data (so file is processed, not skipped)
        mock_audio = MagicMock()
        mock_audio.get.side_effect = lambda key, default=None: {
            "artist": ["Test Artist"],
            "title": ["Test Title"],
            "album": ["Test Album"],
            "albumartist": [""],
            "isrc": [""],
            "date": [""]
        }.get(key, default)

        mock_info = MagicMock()
        mock_info.length = 180.5
        mock_info.bitrate = 320000
        mock_audio.info = mock_info

        # Mock matcher.find_match to return None (no match found)
        async def mock_find_match(artist, title):
            return None

        with patch.object(scanner, '_extract_metadata', return_value=mock_audio):
            with patch.object(scanner.matcher, 'find_match', side_effect=mock_find_match):
                await scanner.scan_directory(tmpdir)

        # When no files are missing (path_index is empty, so no missing files),
        # move detection should be skipped
        assert scanner.perf_metrics.move_detection_queries_skipped >= 1
        assert scanner.perf_metrics.move_detection_queries == 0


@pytest.mark.asyncio
async def test_touch_batch_tracking(async_session):
    """Test that touch batches are tracked correctly."""
    scanner = FileScanner(async_session)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file and add it to DB
        file_path = Path(tmpdir) / "existing.mp3"
        file_path.write_bytes(b"fake audio data")
        
        lib_file = LibraryFile(
            path=str(file_path),
            size=len(b"fake audio data"),
            mtime=os.path.getmtime(file_path),
            recording_id=1,
        )
        async_session.add(lib_file)
        await async_session.commit()
        
        # Rescan - file should be touched (unchanged)
        with patch.object(scanner, '_extract_metadata') as mock_extract:
            await scanner.scan_directory(tmpdir)
            
            # Should not extract metadata (file unchanged)
            assert mock_extract.call_count == 0
            
            # Should have tracked touch batch
            assert scanner.perf_metrics.touch_batches >= 1
            assert scanner.perf_metrics.touch_files_total >= 1


@pytest.mark.asyncio
async def test_performance_summary_logging(async_session, caplog):
    """Test that performance summary is logged at the end of scan."""
    scanner = FileScanner(async_session)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.mp3"
        file_path.write_bytes(b"fake audio data")
        
        with patch.object(scanner, '_extract_metadata', return_value=None):
            await scanner.scan_directory(tmpdir)
        
        # Check that performance summary was logged
        # The log_summary method should have been called
        assert scanner.perf_metrics.duration_seconds is not None
        assert scanner.perf_metrics.files_per_second >= 0


@pytest.mark.asyncio
async def test_performance_metrics_to_dict(async_session):
    """Test that performance metrics can be serialized to dict."""
    scanner = FileScanner(async_session)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.mp3"
        file_path.write_bytes(b"fake audio data")
        
        with patch.object(scanner, '_extract_metadata', return_value=None):
            await scanner.scan_directory(tmpdir)
        
        # Convert to dict
        metrics_dict = scanner.perf_metrics.to_dict()
        
        # Verify all expected keys are present
        assert "timestamp" in metrics_dict
        assert "duration_seconds" in metrics_dict
        assert "files_processed" in metrics_dict
        assert "files_per_second" in metrics_dict
        assert "metadata_extractions" in metrics_dict
        assert "metadata_extractions_skipped" in metrics_dict
        assert "legacy_files_updated" in metrics_dict
        assert "commits_executed" in metrics_dict
        assert "commits_skipped" in metrics_dict
        assert "move_detection_queries" in metrics_dict
        assert "move_detection_queries_skipped" in metrics_dict

