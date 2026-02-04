"""Comprehensive tests for the FileScanner module.

This test suite covers:
- Directory scanning and file discovery
- Metadata extraction from various audio formats
- Artist/Work/Recording deduplication
- Progress tracking
- Error handling for corrupt/missing files
- File hash calculation
- Vector DB indexing
"""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from airwave.core.models import Artist, LibraryFile, Recording, Work
from airwave.core.stats import ScanStats
from airwave.worker.scanner import FileScanner, LibraryMetadata
from sqlalchemy import select


class TestLibraryMetadata:
    """Test the LibraryMetadata air-lock class."""

    def test_metadata_normalization(self):
        """Test that metadata is normalized on initialization."""
        meta = LibraryMetadata(
            raw_artist="The Beatles",
            raw_title="Let It Be (Remastered 2009)",
            album_title="Let It Be",
        )

        assert meta.raw_artist == "The Beatles"
        assert meta.artist == "beatles"  # Normalized
        assert meta.title == "let it be"  # Version tag removed
        assert meta.version_type == "Remastered"
        assert meta.work_title == "let it be"

    def test_metadata_version_extraction(self):
        """Test version type extraction from titles."""
        # Live version
        meta_live = LibraryMetadata(
            raw_artist="Nirvana", raw_title="Smells Like Teen Spirit (Live)"
        )
        assert meta_live.version_type == "Live"
        assert meta_live.title == "smells like teen spirit"

        # Remix version
        meta_remix = LibraryMetadata(
            raw_artist="Daft Punk", raw_title="Get Lucky [Remix]"
        )
        assert meta_remix.version_type == "Remix"

        # Original (no version tag)
        meta_orig = LibraryMetadata(
            raw_artist="Queen", raw_title="Bohemian Rhapsody"
        )
        assert meta_orig.version_type == "Original"

    def test_metadata_album_artist_fallback(self):
        """Test that album_artist defaults to track artist."""
        meta = LibraryMetadata(raw_artist="Pink Floyd", raw_title="Comfortably Numb")
        assert meta.album_artist == "pink floyd"

        meta_with_album = LibraryMetadata(
            raw_artist="Various Artists",
            raw_title="Song",
            album_artist="Compilation",
        )
        assert meta_with_album.album_artist == "compilation"

    def test_metadata_handles_missing_values(self):
        """Test metadata handles None/empty values gracefully."""
        meta = LibraryMetadata(raw_artist=None, raw_title=None)
        assert meta.artist == "unknown artist"
        assert meta.title == "untitled"


class TestFileScanner:
    """Test the FileScanner class."""

    @pytest.mark.asyncio
    async def test_scanner_initialization(self, db_session):
        """Test scanner initializes with session and matcher."""
        scanner = FileScanner(db_session)
        assert scanner.session == db_session
        assert scanner.matcher is not None
        assert scanner.executor is not None
        assert scanner.SUPPORTED_EXTENSIONS == {".mp3", ".flac", ".m4a", ".wav", ".ogg"}

    @pytest.mark.asyncio
    async def test_scan_directory_not_found(self, db_session):
        """Test scan_directory handles non-existent directory."""
        scanner = FileScanner(db_session)
        result = await scanner.scan_directory("/nonexistent/path")

        assert result.errors == 1

    @pytest.mark.asyncio
    async def test_get_or_create_artist_new(self, db_session):
        """Test creating a new artist."""
        scanner = FileScanner(db_session)
        artist = await scanner._get_or_create_artist("nirvana")

        assert artist.name == "nirvana"
        assert artist.id is not None

    @pytest.mark.asyncio
    async def test_get_or_create_artist_existing(self, db_session):
        """Test retrieving an existing artist."""
        # Create artist first
        existing = Artist(name="pearl jam")
        db_session.add(existing)
        await db_session.flush()

        scanner = FileScanner(db_session)
        artist = await scanner._get_or_create_artist("pearl jam")

        assert artist.id == existing.id
        assert artist.name == "pearl jam"

    @pytest.mark.asyncio
    async def test_get_or_create_artist_empty_name(self, db_session):
        """Test artist creation with empty name defaults to 'unknown artist'."""
        scanner = FileScanner(db_session)
        artist = await scanner._get_or_create_artist("")

        assert artist.name == "unknown artist"

    @pytest.mark.asyncio
    async def test_get_or_create_work_new(self, db_session):
        """Test creating a new work."""
        # Create artist first
        artist = Artist(name="radiohead")
        db_session.add(artist)
        await db_session.flush()

        scanner = FileScanner(db_session)
        work = await scanner._get_or_create_work("creep", artist.id)

        assert work.title == "creep"
        assert work.artist_id == artist.id

    @pytest.mark.asyncio
    async def test_get_or_create_work_existing(self, db_session):
        """Test retrieving an existing work."""
        # Create artist and work
        artist = Artist(name="foo fighters")
        db_session.add(artist)
        await db_session.flush()

        existing_work = Work(title="everlong", artist_id=artist.id)
        db_session.add(existing_work)
        await db_session.flush()

        scanner = FileScanner(db_session)
        work = await scanner._get_or_create_work("everlong", artist.id)

        assert work.id == existing_work.id

    @pytest.mark.asyncio
    async def test_get_or_create_recording_new(self, db_session):
        """Test creating a new recording."""
        # Create artist and work
        artist = Artist(name="metallica")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="enter sandman", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        scanner = FileScanner(db_session)
        recording = await scanner._get_or_create_recording(
            work.id, "enter sandman", "Original", duration=331.0, isrc="USEE10001993"
        )

        assert recording.work_id == work.id
        assert recording.title == "enter sandman"
        assert recording.version_type == "Original"
        assert recording.duration == 331.0
        assert recording.isrc == "USEE10001993"

    @pytest.mark.asyncio
    async def test_get_or_create_recording_existing(self, db_session):
        """Test retrieving an existing recording."""
        # Create hierarchy
        artist = Artist(name="acdc")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="back in black", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        existing_rec = Recording(
            work_id=work.id, title="back in black", version_type="Original"
        )
        db_session.add(existing_rec)
        await db_session.flush()

        scanner = FileScanner(db_session)
        recording = await scanner._get_or_create_recording(
            work.id, "back in black", "Original"
        )

        assert recording.id == existing_rec.id

    @pytest.mark.asyncio
    async def test_get_or_create_recording_updates_isrc(self, db_session):
        """Test that ISRC is updated if missing on existing recording."""
        # Create recording without ISRC
        artist = Artist(name="led zeppelin")
        db_session.add(artist)
        await db_session.flush()

        work = Work(title="stairway to heaven", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()

        existing_rec = Recording(
            work_id=work.id, title="stairway to heaven", version_type="Original"
        )
        db_session.add(existing_rec)
        await db_session.flush()

        assert existing_rec.isrc is None

        scanner = FileScanner(db_session)
        recording = await scanner._get_or_create_recording(
            work.id, "stairway to heaven", "Original", isrc="USLED7100123"
        )

        assert recording.id == existing_rec.id
        assert recording.isrc == "USLED7100123"

    @pytest.mark.asyncio
    async def test_process_file_skips_existing(self, db_session):
        """Test that process_file skips files already in database."""
        # Create a file record
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
        await db_session.flush()

        existing_file = LibraryFile(
            recording_id=recording.id,
            path="/test/path.mp3",
            size=1000,
            format="mp3",
        )
        db_session.add(existing_file)
        await db_session.commit()

        scanner = FileScanner(db_session)
        stats = ScanStats()

        # Mock the file path
        with patch.object(Path, "exists", return_value=True):
            await scanner.process_file(Path("/test/path.mp3"), stats)

        assert stats.skipped == 1
        assert stats.created == 0

    @pytest.mark.asyncio
    async def test_calculate_file_hash(self, db_session):
        """Test MD5 hash calculation for files."""
        scanner = FileScanner(db_session)

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, mode="wb") as f:
            f.write(b"test content for hashing")
            temp_path = Path(f.name)

        try:
            file_hash = scanner._calculate_file_hash(temp_path)
            assert file_hash is not None
            assert len(file_hash) == 32  # MD5 hash is 32 hex characters
            # MD5 of b"test content for hashing"
            assert file_hash == "8454e1a036eeaf298bb90b7b7c9723fd"
        finally:
            temp_path.unlink()

    @pytest.mark.asyncio
    async def test_extract_metadata_handles_corrupt_file(self, db_session):
        """Test metadata extraction handles corrupt files gracefully."""
        scanner = FileScanner(db_session)

        # Create a corrupt file (not a valid audio file)
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".mp3", mode="wb"
        ) as f:
            f.write(b"not a valid mp3 file")
            temp_path = Path(f.name)

        try:
            result = scanner._extract_metadata(temp_path)
            # Should return None for corrupt files
            assert result is None
        finally:
            temp_path.unlink()

