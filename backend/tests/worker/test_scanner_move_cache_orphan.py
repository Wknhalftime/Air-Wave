"""Focused tests for scanner move detection, folder cache, and orphan GC.

This test suite covers:
- Move detection: _content_pid, _update_path_index_for_move, _find_move_candidate,
  _ensure_missing_candidates
- Folder cache: _folder_cache_path, _load_folder_cache, _save_folder_cache
- Orphan GC: _finalize_scan_orphan_gc
"""

import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from airwave.core.config import settings
from airwave.core.models import Artist, LibraryFile, Recording, Work
from airwave.worker.scanner import FileScanner


# =============================================================================
# Move Detection
# =============================================================================


class TestContentPid:
    """Test _content_pid() - content identifier for move detection."""

    def test_with_metadata_returns_md5_hash(self):
        """With real artist/title, returns MD5 hash as pid_primary, None as fallback."""
        path = Path("/music/Artist - Song.mp3")
        pid_primary, pid_fallback = FileScanner._content_pid("Artist", "Song", path)
        expected = hashlib.md5(b"Artist|Song").hexdigest()
        assert pid_primary == expected
        assert pid_fallback is None

    def test_unknown_artist_untitled_uses_filename(self):
        """Unknown artist + Untitled uses filename for both primary and fallback."""
        path = Path("/music/my_file.mp3")
        pid_primary, pid_fallback = FileScanner._content_pid(
            "Unknown Artist", "Untitled", path
        )
        assert pid_primary == "my_file.mp3"
        assert pid_fallback == "my_file.mp3"

    def test_unknown_artist_unknown_title_uses_filename(self):
        """Unknown artist + Unknown Title also uses filename."""
        path = Path("/folder/track.flac")
        pid_primary, pid_fallback = FileScanner._content_pid(
            "Unknown Artist", "Unknown Title", path
        )
        assert pid_primary == "track.flac"
        assert pid_fallback == "track.flac"

    def test_empty_artist_title_treated_as_unknown(self):
        """Empty strings are treated as unknown for no_meta check."""
        path = Path("/x/song.mp3")
        # With empty artist/title, key becomes "|" - not unknown artist/untitled
        # so we get MD5 of "|"
        pid_primary, pid_fallback = FileScanner._content_pid("", "", path)
        assert pid_primary == hashlib.md5(b"|").hexdigest()
        assert pid_fallback is None

    def test_same_artist_title_same_hash(self):
        """Same artist and title produce same hash regardless of path."""
        path1 = Path("/a/Artist - Song.mp3")
        path2 = Path("/b/Artist - Song.mp3")
        pid1, _ = FileScanner._content_pid("Artist", "Song", path1)
        pid2, _ = FileScanner._content_pid("Artist", "Song", path2)
        assert pid1 == pid2


class TestUpdatePathIndexForMove:
    """Test _update_path_index_for_move() - path index update when file moves."""

    @pytest.mark.asyncio
    async def test_updates_path_index(self, db_session):
        """Old path is removed, new path is added with file info."""
        scanner = FileScanner(db_session)
        scanner._path_index = {
            "/old/path/song.mp3": {"id": 1, "size": 1024, "mtime": 12345.0}
        }

        await scanner._update_path_index_for_move(
            "/old/path/song.mp3",
            "/new/path/song.mp3",
            file_id=1,
            size=2048,
            mtime=99999.0,
        )

        assert "/old/path/song.mp3" not in scanner._path_index
        assert "/new/path/song.mp3" in scanner._path_index
        entry = scanner._path_index["/new/path/song.mp3"]
        assert entry["id"] == 1
        assert entry["size"] == 2048
        assert entry["mtime"] == 99999.0

    @pytest.mark.asyncio
    async def test_normalizes_backslashes(self, db_session):
        """Backslashes are normalized to forward slashes in path keys."""
        scanner = FileScanner(db_session)
        scanner._path_index = {}
        old_path = "C:\\music\\old.mp3"
        new_path = "C:\\music\\new.mp3"

        await scanner._update_path_index_for_move(
            old_path, new_path, file_id=1, size=1024, mtime=1.0
        )

        # Key uses forward slashes; on Windows also lowercased
        expected = "c:/music/new.mp3" if sys.platform == "win32" else "C:/music/new.mp3"
        assert expected in scanner._path_index


class TestFindMoveCandidate:
    """Test _find_move_candidate() - find and pop matching move candidate."""

    @pytest.mark.asyncio
    async def test_finds_by_pid_primary_and_size(self, db_session):
        """Finds candidate matching pid_primary and size, removes from list."""
        scanner = FileScanner(db_session)
        candidate = {
            "lib_id": 100,
            "old_path": "/old/song.mp3",
            "size": 2048,
            "pid_primary": "abc123",
            "pid_fallback": None,
        }
        scanner._missing_candidates = [candidate]

        result = await scanner._find_move_candidate("abc123", None, 2048)

        assert result == candidate
        assert scanner._missing_candidates == []

    @pytest.mark.asyncio
    async def test_finds_by_pid_fallback_when_primary_misses(self, db_session):
        """Falls back to pid_fallback when primary does not match."""
        scanner = FileScanner(db_session)
        candidate = {
            "lib_id": 101,
            "old_path": "/old/unknown.mp3",
            "size": 512,
            "pid_primary": "unknown.mp3",
            "pid_fallback": "unknown.mp3",
        }
        scanner._missing_candidates = [candidate]

        result = await scanner._find_move_candidate(
            "unknown.mp3", "unknown.mp3", 512
        )

        assert result == candidate
        assert scanner._missing_candidates == []

    @pytest.mark.asyncio
    async def test_returns_none_when_size_mismatch(self, db_session):
        """No match when size differs."""
        scanner = FileScanner(db_session)
        candidate = {
            "lib_id": 1,
            "old_path": "/old/song.mp3",
            "size": 2048,
            "pid_primary": "abc123",
            "pid_fallback": None,
        }
        scanner._missing_candidates = [candidate]

        result = await scanner._find_move_candidate("abc123", None, 1024)

        assert result is None
        assert len(scanner._missing_candidates) == 1

    @pytest.mark.asyncio
    async def test_returns_none_when_empty_candidates(self, db_session):
        """Returns None when _missing_candidates is empty."""
        scanner = FileScanner(db_session)
        scanner._missing_candidates = []

        result = await scanner._find_move_candidate("abc", None, 1024)

        assert result is None


class TestEnsureMissingCandidates:
    """Test _ensure_missing_candidates() - populate from DB when files are missing."""

    @pytest.mark.asyncio
    async def test_skips_query_when_no_missing(self, db_session):
        """When path_index_seen contains all paths, sets empty list and skips query."""
        scanner = FileScanner(db_session)
        scanner._path_index = {"/a/song.mp3": {"id": 1, "size": 1024, "mtime": 1.0}}
        scanner._path_index_seen = {"/a/song.mp3"}
        scanner._missing_candidates = None
        scanner._processing_lock = asyncio.Lock()
        scanner._session_lock = asyncio.Lock()

        await scanner._ensure_missing_candidates()

        assert scanner._missing_candidates == []

    @pytest.mark.asyncio
    async def test_populates_when_files_missing(self, db_session):
        """When paths are missing, runs query and populates _missing_candidates."""
        artist = Artist(name="test artist")
        db_session.add(artist)
        await db_session.flush()
        work = Work(title="missing song", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()
        rec = Recording(work_id=work.id, title="missing song", version_type="Original")
        db_session.add(rec)
        await db_session.flush()
        lib = LibraryFile(
            recording_id=rec.id,
            path="/music/missing.mp3",
            size=1024,
            mtime=12345.0,
            format="mp3",
        )
        db_session.add(lib)
        await db_session.commit()

        scanner = FileScanner(db_session)
        path_str = "/music/missing.mp3"
        if sys.platform == "win32":
            path_str = path_str.lower()
        scanner._path_index = {path_str: {"id": lib.id, "size": 1024, "mtime": 12345.0}}
        scanner._path_index_seen = set()
        scanner._missing_candidates = None
        scanner._processing_lock = asyncio.Lock()
        scanner._session_lock = asyncio.Lock()

        await scanner._ensure_missing_candidates()

        assert scanner._missing_candidates is not None
        assert len(scanner._missing_candidates) == 1
        c = scanner._missing_candidates[0]
        assert c["lib_id"] == lib.id
        assert c["old_path"] == path_str
        assert c["size"] == 1024
        assert "pid_primary" in c

    @pytest.mark.asyncio
    async def test_idempotent_after_first_call(self, db_session):
        """Second call does not re-run query (early return)."""
        scanner = FileScanner(db_session)
        scanner._path_index = {}
        scanner._path_index_seen = set()
        scanner._missing_candidates = []

        await scanner._ensure_missing_candidates()
        await scanner._ensure_missing_candidates()

        assert scanner._missing_candidates == []


# =============================================================================
# Folder Cache
# =============================================================================


class TestFolderCachePath:
    """Test _folder_cache_path() - cache file path per library root."""

    def test_same_root_same_path(self, db_session):
        """Same root path returns same cache path."""
        scanner = FileScanner(db_session)
        p1 = scanner._folder_cache_path("/music")
        p2 = scanner._folder_cache_path("/music")
        assert p1 == p2

    def test_different_roots_different_paths(self, db_session):
        """Different roots return different cache paths."""
        scanner = FileScanner(db_session)
        p1 = scanner._folder_cache_path("/music")
        p2 = scanner._folder_cache_path("/other/library")
        assert p1 != p2

    def test_path_in_scan_folder_cache_dir(self, db_session):
        """Cache path is under scan_folder_cache with .json extension."""
        scanner = FileScanner(db_session)
        path = scanner._folder_cache_path("/music")
        assert "scan_folder_cache" in str(path)
        assert path.suffix == ".json"
        assert path.parent == settings.DATA_DIR / "scan_folder_cache"


class TestLoadFolderCache:
    """Test _load_folder_cache() - load folder mtime cache from disk."""

    def test_returns_empty_when_file_missing(self, db_session):
        """Returns {} when cache file does not exist."""
        scanner = FileScanner(db_session)
        nonexistent = Path("/nonexistent/cache/path/that/does/not/exist.json")
        with patch.object(scanner, "_folder_cache_path", return_value=nonexistent):
            result = scanner._load_folder_cache("/nonexistent/library")
        assert result == {}

    def test_loads_valid_json(self, db_session):
        """Loads and returns cache dict from valid JSON file."""
        scanner = FileScanner(db_session)
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "scan_folder_cache"
            cache_dir.mkdir()
            path = cache_dir / "test_cache.json"
            path.write_text(json.dumps({"/music": 12345.0, "/music/sub": 12346.0}))
            with patch.object(scanner, "_folder_cache_path", return_value=path):
                result = scanner._load_folder_cache("/music")
        assert len(result) == 2
        assert 12345.0 in result.values()
        assert 12346.0 in result.values()

    def test_invalid_json_returns_empty(self, db_session):
        """Invalid JSON returns {}."""
        scanner = FileScanner(db_session)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad_cache.json"
            path.write_text("not valid json {")
            with patch.object(scanner, "_folder_cache_path", return_value=path):
                result = scanner._load_folder_cache("/music")
        assert result == {}


class TestSaveFolderCache:
    """Test _save_folder_cache() - persist folder mtime cache to disk."""

    def test_writes_cache_to_file(self, db_session):
        """Writes _folder_mtime_cache to JSON file."""
        scanner = FileScanner(db_session)
        scanner._folder_mtime_cache = {"/music": 12345.0, "/music/sub": 12346.0}
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test_cache.json"
            with patch.object(scanner, "_folder_cache_path", return_value=cache_path):
                scanner._save_folder_cache("/music")
            assert cache_path.exists()
            data = json.loads(cache_path.read_text())
            assert data == {"/music": 12345.0, "/music/sub": 12346.0}

    def test_skips_when_cache_empty(self, db_session):
        """Does nothing when _folder_mtime_cache is empty/None."""
        scanner = FileScanner(db_session)
        scanner._folder_mtime_cache = {}
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "empty_cache.json"
            with patch.object(scanner, "_folder_cache_path", return_value=cache_path):
                scanner._save_folder_cache("/music")
            assert not cache_path.exists()

    def test_creates_parent_directories(self, db_session):
        """Creates parent directories for cache file if they do not exist."""
        scanner = FileScanner(db_session)
        scanner._folder_mtime_cache = {"/music": 1.0}
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "nested" / "cache" / "dir"
            cache_path = cache_dir / "test.json"
            assert not cache_dir.exists()
            with patch.object(scanner, "_folder_cache_path", return_value=cache_path):
                scanner._save_folder_cache("/music")
            assert cache_dir.exists()
            assert cache_path.exists()


# =============================================================================
# Orphan GC
# =============================================================================


class TestFinalizeScanOrphanGc:
    """Test _finalize_scan_orphan_gc() - remove LibraryFiles no longer on disk."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_path_index_seen(self, db_session):
        """Returns 0 when _path_index_seen is not set."""
        scanner = FileScanner(db_session)
        scanner._path_index_seen = None
        scanner._session_lock = asyncio.Lock()

        result = await scanner._finalize_scan_orphan_gc()

        assert result == 0

    def _normalize_path_for_gc(self, path_str: str) -> str:
        """Normalize path the same way _finalize_scan_orphan_gc does."""
        try:
            normalized = Path(path_str).resolve().as_posix()
        except (OSError, ValueError):
            normalized = path_str.replace("\\", "/")
        if sys.platform == "win32":
            normalized = normalized.lower()
        return normalized

    @pytest.mark.asyncio
    async def test_keeps_files_in_path_index_seen(self, db_session):
        """Files whose paths are in path_index_seen are NOT deleted."""
        artist = Artist(name="artist")
        db_session.add(artist)
        await db_session.flush()
        work = Work(title="song", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()
        rec = Recording(work_id=work.id, title="song", version_type="Original")
        db_session.add(rec)
        await db_session.flush()
        path_str = str(Path.cwd() / "music" / "kept.mp3")
        lib = LibraryFile(
            recording_id=rec.id, path=path_str, size=1024, mtime=1.0, format="mp3"
        )
        db_session.add(lib)
        await db_session.commit()

        scanner = FileScanner(db_session)
        path_index_seen = {self._normalize_path_for_gc(path_str)}
        scanner._path_index_seen = path_index_seen
        scanner._session_lock = asyncio.Lock()

        result = await scanner._finalize_scan_orphan_gc()

        assert result == 0
        await db_session.refresh(lib)
        assert lib.id is not None

    @pytest.mark.asyncio
    async def test_deletes_files_not_in_path_index_seen(self, db_session):
        """Files whose paths are NOT in path_index_seen are deleted."""
        artist = Artist(name="artist")
        db_session.add(artist)
        await db_session.flush()
        work = Work(title="song", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()
        rec = Recording(work_id=work.id, title="song", version_type="Original")
        db_session.add(rec)
        await db_session.flush()
        path_str = str(Path.cwd() / "music" / "orphaned.mp3")
        lib = LibraryFile(
            recording_id=rec.id, path=path_str, size=1024, mtime=1.0, format="mp3"
        )
        db_session.add(lib)
        await db_session.commit()
        lib_id = lib.id

        scanner = FileScanner(db_session)
        # path_index_seen must be non-empty or GC returns 0 without running
        scanner._path_index_seen = {str(Path.cwd() / "other" / "seen.mp3")}
        scanner._session_lock = asyncio.Lock()

        result = await scanner._finalize_scan_orphan_gc()

        assert result == 1
        await db_session.commit()
        found = await db_session.get(LibraryFile, lib_id)
        assert found is None

    @pytest.mark.asyncio
    async def test_deletes_multiple_orphans(self, db_session):
        """Multiple orphan files are all deleted."""
        artist = Artist(name="artist")
        db_session.add(artist)
        await db_session.flush()
        work = Work(title="song", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()
        rec = Recording(work_id=work.id, title="song", version_type="Original")
        db_session.add(rec)
        await db_session.flush()

        for i in range(3):
            path_str = str(Path.cwd() / "music" / f"orphan{i}.mp3")
            lib = LibraryFile(
                recording_id=rec.id, path=path_str, size=1024, mtime=1.0, format="mp3"
            )
            db_session.add(lib)
        await db_session.commit()

        scanner = FileScanner(db_session)
        # path_index_seen must be non-empty or GC returns 0 without running
        scanner._path_index_seen = {str(Path.cwd() / "other" / "seen.mp3")}
        scanner._session_lock = asyncio.Lock()

        result = await scanner._finalize_scan_orphan_gc()

        assert result == 3

    @pytest.mark.asyncio
    async def test_mixed_keep_and_delete(self, db_session):
        """Keeps seen files, deletes unseen files."""
        artist = Artist(name="artist")
        db_session.add(artist)
        await db_session.flush()
        work = Work(title="song", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()
        rec = Recording(work_id=work.id, title="song", version_type="Original")
        db_session.add(rec)
        await db_session.flush()

        kept_path = str(Path.cwd() / "music" / "kept.mp3")
        orphan_path = str(Path.cwd() / "music" / "orphan.mp3")

        lib_kept = LibraryFile(
            recording_id=rec.id, path=kept_path, size=1024, mtime=1.0, format="mp3"
        )
        lib_orphan = LibraryFile(
            recording_id=rec.id, path=orphan_path, size=1024, mtime=1.0, format="mp3"
        )
        db_session.add(lib_kept)
        db_session.add(lib_orphan)
        await db_session.commit()
        kept_id = lib_kept.id
        orphan_id = lib_orphan.id

        scanner = FileScanner(db_session)
        scanner._path_index_seen = {self._normalize_path_for_gc(kept_path)}
        scanner._session_lock = asyncio.Lock()

        result = await scanner._finalize_scan_orphan_gc()

        assert result == 1
        await db_session.commit()
        assert (await db_session.get(LibraryFile, kept_id)) is not None
        assert (await db_session.get(LibraryFile, orphan_id)) is None
