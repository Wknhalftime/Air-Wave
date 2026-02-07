"""Audio file scanner worker service for music library management.

This module provides functionality to recursively scan directories for audio
files, extract metadata using Mutagen, and sync them to the database. It
handles the complete Artist → Work → Recording → LibraryFile hierarchy and
supports multi-artist collaborations, album associations, and version detection.

The scanner uses thread pool executors for parallel metadata extraction and
integrates with the vector database for semantic indexing.

Typical usage example:
    scanner = FileScanner(session)
    stats = await scanner.scan_directory("/path/to/music", task_id="scan-123")
    print(f"Processed: {stats.processed}, Skipped: {stats.skipped}")
"""

import asyncio
import concurrent.futures
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mutagen
from loguru import logger
from mutagen.id3 import ID3NoHeaderError
from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.core.models import (
    Album,
    Artist,
    LibraryFile,
    ProposedSplit,
    Recording,
    Work,
    WorkArtist,
)
from airwave.core.normalization import Normalizer
from airwave.core.performance import PerformanceMetrics
from airwave.core.scanner_config import ScannerConfig
from airwave.core.stats import ScanStats
from airwave.core.task_store import TaskStore
from airwave.core.vector_db import VectorDB
from airwave.worker.matcher import Matcher


class _ArtistRef:
    """Stand-in for Artist until _flush_pending_artists() fills cache; .id requires flush first."""

    __slots__ = ("_scanner", "_name")

    def __init__(self, scanner: "FileScanner", name: str):
        self._scanner = scanner
        self._name = name

    @property
    def id(self) -> int:
        if self._name not in self._scanner._artist_cache:
            raise RuntimeError(
                f"Artist {self._name!r} not in cache. "
                "Call _flush_pending_artists() before using .id on a newly added artist."
            )
        return self._scanner._artist_cache[self._name].id

    @property
    def name(self) -> str:
        return self._name


class LibraryMetadata:
    """Sanitized metadata container for audio file information.

    This class acts as an "air-lock" between raw file metadata and the
    database, performing normalization and version parsing during initialization.
    It extracts version types (Live, Remix, etc.) and normalizes artist/title
    strings for consistent matching.

    Attributes:
        raw_artist: Original artist string from file metadata.
        raw_title: Original title string from file metadata.
        artist: Normalized artist name for matching.
        title: Normalized track title (version tags removed).
        version_type: Detected version type (e.g., "Live", "Remix", "Original").
        work_title: Cleaned title representing the abstract work.
        album_artist: Normalized album artist (defaults to track artist).
        album_title: Normalized album title.
        duration: Track duration in seconds.
        isrc: International Standard Recording Code.
        release_date: Album/track release date.
    """

    def __init__(
        self,
        raw_artist: str,
        raw_title: str,
        album_artist: Optional[str] = None,
        album_title: Optional[str] = None,
        duration: Optional[float] = None,
        isrc: Optional[str] = None,
        release_date: Optional[datetime] = None,
    ):
        """Initializes metadata with normalization and version parsing.

        Args:
            raw_artist: Raw artist name from file metadata.
            raw_title: Raw track title from file metadata.
            album_artist: Album artist (defaults to track artist if None).
            album_title: Album title.
            duration: Track duration in seconds.
            isrc: International Standard Recording Code.
            release_date: Release date of the track/album.
        """
        self.raw_artist = raw_artist
        self.raw_title = raw_title

        # Immediate normalization for matching
        self.artist = Normalizer.clean_artist(raw_artist or "Unknown Artist")

        # Version parsing extracts tags like "(Live)" or "[Remix]"
        clean_title, version_type = Normalizer.extract_version_type(
            raw_title or "Untitled"
        )

        self.title = Normalizer.clean(clean_title)
        self.version_type = version_type
        self.work_title = self.title  # Work title is the cleaned base title

        self.album_artist = (
            Normalizer.clean_artist(album_artist)
            if album_artist
            else self.artist
        )
        self.album_title = (
            Normalizer.clean(album_title) if album_title else None
        )

        self.duration = duration
        self.isrc = isrc
        self.release_date = release_date


class FileScanner:
    """Recursive audio file scanner with metadata extraction and database sync.

    This class scans directories for supported audio files, extracts metadata
    using Mutagen in parallel via thread pools, and creates/updates the complete
    music library hierarchy (Artist → Work → Recording → LibraryFile).

    The scanner handles:
    - Multi-artist collaborations (feat., with, &, etc.)
    - Album associations
    - Version detection (Live, Remix, etc.)
    - ISRC code tracking
    - Vector database indexing
    - Progress tracking for long operations

    Attributes:
        session: Async SQLAlchemy database session.
        matcher: Matcher instance for duplicate detection.
        vector_db: VectorDB instance for semantic search (injectable).
        config: ScannerConfig instance for configurable behavior.
        executor: Thread pool executor for parallel metadata extraction.
        SUPPORTED_EXTENSIONS: Set of supported audio file extensions.
    """

    SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".m4a", ".wav", ".ogg"}

    def __init__(
        self,
        session: AsyncSession,
        task_store: Optional[TaskStore] = None,
        vector_db: Optional[VectorDB] = None,
        config: Optional[ScannerConfig] = None,
        max_concurrent_files: Optional[int] = None  # Deprecated: use config instead
    ):
        self.session = session
        self.task_store = task_store or TaskStore.get_global()  # Use global if not provided
        self.vector_db = vector_db or VectorDB()  # Create VectorDB if not provided

        # Handle backward compatibility for max_concurrent_files parameter
        if max_concurrent_files is not None and config is None:
            # Create config with custom max_concurrent_files
            config = ScannerConfig(max_concurrent_files=max_concurrent_files)
        elif max_concurrent_files is not None and config is not None:
            # Both provided - config takes precedence, but warn
            logger.warning(
                "Both 'config' and 'max_concurrent_files' provided to FileScanner. "
                "Using 'config' and ignoring 'max_concurrent_files'. "
                "Please use 'config' parameter only."
            )

        self.config = config or ScannerConfig()  # Use default config if not provided
        self.matcher = Matcher(session, vector_db=self.vector_db)  # Inject VectorDB into Matcher
        # Initialize ThreadPool for blocking I/O (mutagen)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        # Performance monitoring
        self.perf_metrics: Optional[PerformanceMetrics] = None
        # Concurrency control
        self._processing_lock = asyncio.Lock()  # For thread-safe stats updates

    # ========== Thread-Safe Helper Methods (Phase 1: Race Condition Fixes) ==========

    async def _mark_path_seen(self, path: str) -> None:
        """Thread-safe: Mark path as seen in this scan."""
        async with self._processing_lock:
            self._path_index_seen.add(path)

    async def _add_touch_id(self, file_id: int) -> None:
        """Thread-safe: Add file ID to touch batch and flush if threshold reached."""
        async with self._processing_lock:
            self._touch_ids.add(file_id)
            if len(self._touch_ids) >= self.config.touch_batch_size:
                await self._flush_touch()

    async def _update_path_index_for_move(
        self, old_path: str, new_path: str, file_id: int, size: int, mtime: float
    ) -> None:
        """Thread-safe: Update path index when file is moved."""
        async with self._processing_lock:
            self._path_index.pop(old_path, None)
            self._path_index[new_path] = {
                "id": file_id,
                "size": size,
                "mtime": mtime,
            }

    def _extract_metadata(self, file_path: Path):
        """Blocking metadata extraction to be run in thread."""
        try:
            return mutagen.File(file_path, easy=True)
        except Exception as e:
            logger.warning(f"Metadata extraction failed for {file_path}: {e}")
            return None

    async def _process_recursive(
        self,
        current_path: str,
        stats: ScanStats,
        task_id: Optional[str]
    ) -> None:
        """Recursively process directory and subdirectories.

        Args:
            current_path: Directory path to process
            stats: Scan statistics (mutable, updated in place)
            task_id: Optional task ID for progress tracking
        """
        # Check for cancellation request (at dir entry and after each batch)
        if task_id and (stats.cancelled or self.task_store.is_cancelled(task_id)):
            if not stats.cancelled:
                stats.cancelled = True
            logger.info(f"Scan cancelled by user at {stats.processed} files")
            return

        try:
            # Track directory processing
            if self.perf_metrics:
                self.perf_metrics.directories_processed += 1

            entries = await asyncio.get_running_loop().run_in_executor(
                None, lambda: list(os.scandir(current_path))
            )

            # Separate files and directories
            files_to_process = []
            dirs_to_process = []

            for entry in entries:
                if entry.is_dir():
                    dirs_to_process.append(entry.path)
                elif entry.is_file():
                    p = Path(entry.path)
                    if p.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                        files_to_process.append(p)

            # Process files in this directory concurrently with semaphore
            if files_to_process:
                await self._process_files_with_semaphore(files_to_process, stats, task_id)

            if stats.cancelled:
                return

            # Recursively process subdirectories (sequentially to avoid too much concurrency)
            for dir_path in dirs_to_process:
                if stats.cancelled:
                    return
                await self._process_recursive(dir_path, stats, task_id)
        except PermissionError:
            logger.warning(f"Permission denied: {current_path}")
        except Exception as e:
            logger.error(f"Error scanning directory {current_path}: {e}")

    async def _process_files_with_semaphore(
        self,
        files_to_process: List[Path],
        stats: ScanStats,
        task_id: Optional[str]
    ) -> None:
        """Process files concurrently with semaphore control.

        Args:
            files_to_process: List of file paths to process
            stats: Scan statistics (mutable, updated in place)
            task_id: Optional task ID for progress tracking
        """
        semaphore = asyncio.Semaphore(self.config.max_concurrent_files)

        # Track last processed count to detect commit boundaries
        last_processed_count = 0
        commit_lock = asyncio.Lock()

        async def process_with_semaphore(file_path):
            nonlocal last_processed_count

            async with semaphore:
                await self.process_file(file_path, stats)

                # Thread-safe progress update and commit check
                async with commit_lock:
                    current_processed = stats.processed
                    prev_processed = last_processed_count
                    last_processed_count = current_processed

                    # Update progress and check for cancellation
                    if task_id and current_processed % self.config.progress_update_interval == 0:
                        self.task_store.update_progress(
                            task_id,
                            current_processed,
                            f"Scanned {current_processed} files ({stats.created} new)",
                        )
                        if self.task_store.is_cancelled(task_id):
                            stats.cancelled = True

                    # Check if we crossed a commit boundary
                    # This handles parallel processing correctly by checking if THIS file
                    # caused us to cross a multiple of commit_interval
                    prev_interval = prev_processed // self.config.commit_interval
                    current_interval = current_processed // self.config.commit_interval

                    if current_interval > prev_interval:
                        # We crossed a commit boundary, check if there are changes
                        has_changes = (
                            stats.created > self._last_commit_created
                            or stats.moved > self._last_commit_moved
                            or len(self._touch_ids) > 0
                            or self.session.new  # New objects added
                            or self.session.dirty  # Existing objects modified
                        )

                        if has_changes:
                            touch_count = len(self._touch_ids)
                            await self._flush_touch()  # Flush pending touch updates
                            await self.session.commit()
                            # Update last commit counters
                            self._last_commit_created = stats.created
                            self._last_commit_moved = stats.moved
                            # Performance tracking
                            if self.perf_metrics:
                                self.perf_metrics.commits_executed += 1
                            logger.debug(
                                f"Committed at {current_processed} files "
                                f"(created={stats.created}, moved={stats.moved}, "
                                f"touched={touch_count})"
                            )
                        else:
                            # Performance tracking
                            if self.perf_metrics:
                                self.perf_metrics.commits_skipped += 1
                            logger.debug(
                                f"Skipped commit at {current_processed} files (no changes)"
                            )

        # Process all files in this directory concurrently
        await asyncio.gather(*[process_with_semaphore(f) for f in files_to_process])

    async def scan_directory(
        self, root_path: str, task_id: Optional[str] = None
    ) -> ScanStats:
        """Recursively scans a directory for audio files and syncs them to DB.

        Returns:
            ScanStats object with processing statistics.
        """
        root = Path(root_path)
        if not root.exists():
            logger.error(f"Directory not found: {root_path}")
            if task_id:
                self.task_store.complete_task(
                    task_id, success=False, error="Directory not found"
                )
            # Return empty stats with error counted
            error_stats = ScanStats()
            error_stats.errors = 1
            return error_stats

        stats = ScanStats()

        # Initialize performance monitoring
        self.perf_metrics = PerformanceMetrics()
        self.perf_metrics.max_concurrent_files = self.config.max_concurrent_files

        if task_id:
            self.task_store.update_total(task_id, 0, "Starting scan...")
        logger.info(f"Starting scan of {root_path}... (parallel processing with max {self.config.max_concurrent_files} concurrent files)")

        # Load path index (id, path, size, mtime) for stat-first skip without per-file DB hit
        # Normalize paths to use forward slashes for cross-platform compatibility
        stmt = select(LibraryFile.id, LibraryFile.path, LibraryFile.size, LibraryFile.mtime)
        result = await self.session.execute(stmt)
        path_index: Dict[str, Dict[str, Any]] = {}
        for row in result.all():
            # Normalize path to use forward slashes (cross-platform)
            normalized_path = row.path.replace("\\", "/")
            path_index[normalized_path] = {"id": row.id, "size": row.size, "mtime": row.mtime}
        self._path_index = path_index
        self._path_index_seen: set = set()
        self._touch_ids: set = set()
        self._missing_candidates: Optional[List[Dict[str, Any]]] = None
        self._artist_cache: Dict[str, Artist] = {}
        self._pending_artists: set = set()
        self._work_cache: Dict[Tuple[str, int], Work] = {}
        self._pending_works: List[Tuple[str, int]] = []
        self._vector_tracks_to_add: List[Tuple[int, str, str]] = []
        self._last_commit_created: int = 0  # Track created count at last commit
        self._last_commit_moved: int = 0    # Track moved count at last commit
        logger.info(f"Loaded path index: {len(path_index)} files")

        # Recursive Scan using scandir with parallel file processing
        await self._process_recursive(root_path, stats, task_id)

        # Check if scan was cancelled
        if task_id and self.task_store.is_cancelled(task_id):
            # Flush any pending changes before cancelling
            await self._flush_touch()
            self._flush_vector_tracks()
            await self.session.commit()

            self.task_store.mark_cancelled(task_id)
            logger.warning(f"Scan cancelled after processing {stats.processed} files")
            return stats

        await self._flush_touch()
        self._flush_vector_tracks()
        await self.session.commit()

        # Finalize performance metrics
        if self.perf_metrics:
            self.perf_metrics.files_processed = stats.processed
            self.perf_metrics.files_skipped = stats.skipped
            self.perf_metrics.files_created = stats.created
            self.perf_metrics.files_moved = stats.moved
            self.perf_metrics.files_errored = stats.errors
            self.perf_metrics.finish()
            self.perf_metrics.log_summary("Scanner")

        if task_id:
            self.task_store.complete_task(task_id, success=True)
            logger.success(f"Task {task_id} completed: {stats}")

        return stats

    def _flush_vector_tracks(self) -> None:
        """Flush queued (recording_id, artist, title) to vector DB in one batch."""
        buf = getattr(self, "_vector_tracks_to_add", None)
        if not buf:
            return
        tracks = list(buf)
        buf.clear()
        if tracks:
            self.vector_db.add_tracks(tracks)

    async def _flush_touch(self) -> None:
        """Batch-update updated_at for LibraryFile ids in _touch_ids (TOUCH path)."""
        touch_ids = getattr(self, "_touch_ids", None)
        if not touch_ids:
            return
        ids_list = list(touch_ids)
        touch_count = len(ids_list)
        self._touch_ids.clear()
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(LibraryFile).where(LibraryFile.id.in_(ids_list)).values(updated_at=now)
        )
        # Performance tracking
        if self.perf_metrics:
            self.perf_metrics.touch_batches += 1
            self.perf_metrics.touch_files_total += touch_count
            self.perf_metrics.db_queries_update += 1

    @staticmethod
    def _content_pid(artist: str, title: str, file_path: Path) -> Tuple[str, Optional[str]]:
        """Content PID for move detection. With metadata: hash(artist|title); without: filename.
        Returns (pid_primary, pid_fallback). pid_fallback is filename when no real metadata."""
        no_meta = (
            (artist or "").lower() == "unknown artist"
            and (title or "").lower() in ("untitled", "unknown title")
        )
        if no_meta:
            return (file_path.name, file_path.name)
        key = f"{(artist or '').strip()}|{(title or '').strip()}"
        return (hashlib.md5(key.encode()).hexdigest(), None)

    async def _ensure_missing_candidates(self) -> None:
        """Populate _missing_candidates from DB: LibraryFiles whose path was not seen this scan."""
        if self._missing_candidates is not None:
            return

        # FIX 4: Skip expensive 4-table JOIN query if no files are missing
        missing_paths = set(self._path_index.keys()) - self._path_index_seen
        if not missing_paths:
            self._missing_candidates = []
            # Performance tracking
            if self.perf_metrics:
                self.perf_metrics.move_detection_queries_skipped += 1
            logger.debug("No missing files detected - skipping move detection query")
            return
        # Files are missing - need to check for moves
        path_list = list(missing_paths)
        # Performance tracking
        if self.perf_metrics:
            self.perf_metrics.move_detection_queries += 1
        logger.info(f"Detected {len(missing_paths)} missing files - running move detection query")
        self._missing_candidates = []
        for start in range(0, len(path_list), self.config.missing_chunk_size):
            chunk = path_list[start : start + self.config.missing_chunk_size]
            stmt = (
                select(LibraryFile.id, LibraryFile.path, LibraryFile.size, Artist.name, Work.title)
                .select_from(LibraryFile)
                .join(Recording, LibraryFile.recording_id == Recording.id)
                .join(Work, Recording.work_id == Work.id)
                .outerjoin(Artist, Work.artist_id == Artist.id)
                .where(LibraryFile.path.in_(chunk))
            )
            result = await self.session.execute(stmt)
            rows = result.all()
            for row in rows:
                artist_name = (row.name or "unknown artist").strip()
                work_title = (row.title or "untitled").strip()
                no_meta = artist_name.lower() == "unknown artist" and work_title.lower() in (
                    "untitled",
                    "unknown title",
                )
                if no_meta:
                    pid_primary = Path(row.path).name
                    pid_fallback = pid_primary
                else:
                    pid_primary = hashlib.md5(f"{artist_name}|{work_title}".encode()).hexdigest()
                    pid_fallback = None
                self._missing_candidates.append({
                    "lib_id": row.id,
                    "old_path": row.path,
                    "size": row.size,
                    "pid_primary": pid_primary,
                    "pid_fallback": pid_fallback,
                })

    async def _find_move_candidate(
        self, pid_primary: str, pid_fallback: Optional[str], size: int
    ) -> Optional[Dict[str, Any]]:
        """Find a missing LibraryFile matching (PID, size). Removes it from _missing_candidates.

        Thread-safe: Protected by _processing_lock to prevent concurrent list mutations.
        """
        async with self._processing_lock:
            if not self._missing_candidates:
                return None
            for i, c in enumerate(self._missing_candidates):
                if c["size"] != size:
                    continue
                if c["pid_primary"] == pid_primary:
                    return self._missing_candidates.pop(i)
                if pid_fallback and c["pid_fallback"] and c["pid_fallback"] == pid_fallback:
                    return self._missing_candidates.pop(i)
            return None

    async def _flush_pending_artists(self) -> None:
        """Bulk insert pending artists and fill _artist_cache."""
        pending = getattr(self, "_pending_artists", None)
        if not pending:
            return
        names = list(pending)
        self._pending_artists.clear()
        await self.session.execute(
            insert(Artist), [{"name": n} for n in names]
        )
        await self.session.flush()
        res = await self.session.execute(select(Artist).where(Artist.name.in_(names)))
        for a in res.scalars().all():
            self._artist_cache[a.name] = a

    async def _flush_pending_works(self) -> None:
        """Bulk insert pending works and fill _work_cache."""
        pending = getattr(self, "_pending_works", None)
        if not pending:
            return
        pairs = list(pending)
        self._pending_works.clear()
        await self.session.execute(
            insert(Work),
            [{"title": t, "artist_id": a} for t, a in pairs],
        )
        await self.session.flush()
        stmt = select(Work).where(
            or_(*(and_(Work.title == t, Work.artist_id == a) for t, a in pairs))
        )
        res = await self.session.execute(stmt)
        for w in res.scalars().all():
            self._work_cache[(w.title, w.artist_id)] = w

    def _ensure_batch_caches(self) -> None:
        """Init artist/work caches and pending when not set (e.g. standalone tests)."""
        if hasattr(self, "_artist_cache") and isinstance(self._artist_cache, dict):
            return
        self._artist_cache = {}
        self._pending_artists = set()
        self._work_cache = {}
        self._pending_works = []

    async def _get_or_create_artist(self, clean_name: str):
        """Get or create artist (batched). Call _flush_pending_artists() before using .id."""
        if not clean_name:
            clean_name = "unknown artist"
        self._ensure_batch_caches()
        if clean_name in self._artist_cache:
            return self._artist_cache[clean_name]
        # Check DB for existing (e.g. from another session or test pre-seed)
        stmt = select(Artist).where(Artist.name == clean_name)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            self._artist_cache[clean_name] = existing
            return existing
        self._pending_artists.add(clean_name)
        return _ArtistRef(self, clean_name)

    async def _get_or_create_work(
        self, clean_title: str, artist_id: int
    ) -> Work:
        """Get or create work using pre-cleaned title (batched inserts).
        Call _flush_pending_works() before using .id if work was just added."""
        self._ensure_batch_caches()
        key = (clean_title, artist_id)
        if key in self._work_cache:
            return self._work_cache[key]
        stmt = select(Work).where(
            Work.title == clean_title, Work.artist_id == artist_id
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            self._work_cache[key] = existing
            return existing
        self._pending_works.append(key)
        await self._flush_pending_works()
        return self._work_cache[key]

    async def _get_or_create_recording(
        self,
        work_id: int,
        clean_title: str,
        version_type: str,
        duration: float = None,
        isrc: str = None,
    ) -> Recording:
        """Get or create recording using pre-cleaned title.

        NOTE: Caller must hold _processing_lock to prevent race conditions.
        """
        stmt = select(Recording).where(
            Recording.work_id == work_id, Recording.title == clean_title
        )
        res = await self.session.execute(stmt)
        recording = res.scalar_one_or_none()

        if not recording:
            recording = Recording(
                work_id=work_id,
                title=clean_title,
                version_type=version_type,
                duration=duration,
                isrc=isrc,
            )
            self.session.add(recording)
            await self.session.flush()
        elif isrc and not recording.isrc:
            recording.isrc = isrc

        return recording

    async def _get_or_create_album(
        self,
        clean_album_title: str,
        artist_id: int,
        release_date: datetime = None,
    ) -> Album:
        """Get or create an album using pre-cleaned title.

        NOTE: Caller must hold _processing_lock to prevent race conditions.
        """
        stmt = select(Album).where(
            Album.title == clean_album_title, Album.artist_id == artist_id
        )
        res = await self.session.execute(stmt)
        album = res.scalar_one_or_none()

        if not album:
            album = Album(
                title=clean_album_title,
                artist_id=artist_id,
                release_date=release_date,
            )
            self.session.add(album)
            await self.session.flush()

        return album

    def _parse_metadata_from_audio(
        self, audio: Any, file_path: Path
    ) -> Tuple[str, str, str, str, Optional[str], Optional[datetime], Optional[float], Optional[int]]:
        """Parse metadata from audio tags.

        Args:
            audio: Mutagen audio object with metadata tags.
            file_path: Path to the audio file (for fallback parsing).

        Returns:
            Tuple of (artist_name, album_artist, title, album_title, isrc, release_date, duration, bitrate)
        """
        # Extract basic metadata
        artist_name = audio.get("artist", [""])[0]
        album_artist = audio.get("albumartist", [""])[0]
        title = audio.get("title", [""])[0]
        album_title = audio.get("album", [""])[0]
        isrc = audio.get("isrc", [""])[0] or None
        date_str = audio.get("date", [""])[0] or None

        # Parse release date (ID3 tags often have just year like "2003")
        release_date = None
        if date_str:
            try:
                # Try parsing full date first (YYYY-MM-DD)
                if len(date_str) == 10 and "-" in date_str:
                    release_date = datetime.strptime(date_str, "%Y-%m-%d")
                # Try year only (YYYY)
                elif len(date_str) == 4 and date_str.isdigit():
                    release_date = datetime(int(date_str), 1, 1)
                # Try YYYY-MM
                elif len(date_str) == 7 and date_str.count("-") == 1:
                    release_date = datetime.strptime(date_str, "%Y-%m")
            except (ValueError, TypeError):
                logger.debug(f"Could not parse date: {date_str}")

        # Extract audio info
        duration = audio.info.length if audio.info else None
        bitrate = getattr(audio.info, "bitrate", None) if audio.info else None

        return (artist_name, album_artist, title, album_title, isrc, release_date, duration, bitrate)

    def _apply_filename_fallback(
        self, raw_artist: str, raw_title: str, file_path: Path
    ) -> Tuple[str, str]:
        """Apply filename parsing fallback if tags are missing or generic.

        Args:
            raw_artist: Artist name from tags.
            raw_title: Title from tags.
            file_path: Path to the audio file.

        Returns:
            Tuple of (raw_artist, raw_title) with fallback applied if needed.
        """
        if (
            not raw_artist
            or not raw_title
            or raw_artist.lower() == "unknown"
            or raw_title.lower() == "untitled"
        ):
            stem = file_path.stem
            if " - " in stem:
                parts = stem.split(" - ", 1)
                raw_artist = raw_artist or parts[0]
                raw_title = raw_title or parts[1]
            else:
                raw_title = raw_title or stem
                raw_artist = raw_artist or "Unknown Artist"

        return (raw_artist, raw_title)

    async def _check_ambiguous_artist_split(
        self, raw_artist: str, album_artist: str
    ) -> None:
        """Detect and flag ambiguous artist splits for manual review.

        Args:
            raw_artist: Raw artist string from metadata.
            album_artist: Album artist string from metadata.
        """
        # Only check if there's a "/" and no album artist to guide us
        if "/" in raw_artist and not album_artist:
            stmt = select(ProposedSplit).where(
                ProposedSplit.raw_artist == raw_artist
            )
            res = await self.session.execute(stmt)
            if not res.scalar_one_or_none():
                # Determine how to split
                if " / " in raw_artist:
                    proposed = Normalizer.split_artists(raw_artist)
                else:
                    proposed = [
                        p.strip()
                        for p in raw_artist.split("/")
                        if p.strip()
                    ]

                self.session.add(
                    ProposedSplit(
                        raw_artist=raw_artist,
                        proposed_artists=proposed,
                        status="PENDING",
                        confidence=0.5,
                    )
                )
                logger.info(
                    f"Flagged ambiguous artist for review: {raw_artist}"
                )

    async def _link_multi_artists(
        self, work: Work, primary_artist, raw_artist: str, album_artist: str
    ) -> None:
        """Link all artists (primary + featured) to the work.

        Args:
            work: Work object to link artists to.
            primary_artist: Primary artist object or _ArtistRef.
            raw_artist: Raw artist string from metadata.
            album_artist: Album artist string from metadata.
        """
        # Split all names processed in Meta
        all_raw_candidates = [raw_artist]
        if album_artist:
            all_raw_candidates.append(album_artist)

        unique_targets = set()
        for raw in all_raw_candidates:
            for a in Normalizer.split_artists(raw):
                unique_targets.add(Normalizer.clean_artist(a))

        for a_clean in unique_targets:
            a_obj = await self._get_or_create_artist(a_clean)
            await self._flush_pending_artists()
            stmt_wa = select(WorkArtist).where(
                WorkArtist.work_id == work.id,
                WorkArtist.artist_id == a_obj.id,
            )
            res_wa = await self.session.execute(stmt_wa)
            if not res_wa.scalar_one_or_none():
                role = (
                    "Primary"
                    if a_obj.id == primary_artist.id
                    else "Featured"
                )
                self.session.add(
                    WorkArtist(
                        work_id=work.id, artist_id=a_obj.id, role=role
                    )
                )

    async def _create_library_file(
        self,
        recording: Recording,
        file_path: Path,
        file_hash: str,
        bitrate: Optional[int],
        mtime: Optional[float] = None,
    ) -> LibraryFile:
        """Create and persist a LibraryFile record.

        Args:
            recording: Recording object to link the file to.
            file_path: Path to the audio file.
            file_hash: MD5 hash of the file.
            bitrate: Bitrate of the audio file.
            mtime: Optional filesystem mtime (st_mtime) for scan index.

        Returns:
            The created LibraryFile object.

        Raises:
            OSError: If the file cannot be stat'd (e.g. deleted between stat and create).
        """
        try:
            st = file_path.stat()
        except OSError as e:
            logger.warning(f"File gone or inaccessible when creating LibraryFile {file_path}: {e}")
            raise
        new_file = LibraryFile(
            recording_id=recording.id,
            path=str(file_path),
            size=st.st_size,
            mtime=(mtime if mtime is not None else float(st.st_mtime)),
            format=file_path.suffix.replace(".", ""),
            file_hash=file_hash,
            bitrate=bitrate,
        )
        self.session.add(new_file)
        await self.session.flush()
        return new_file

    # ========== Phase 5: Extracted Methods for process_file() ==========

    def _ensure_scan_state_initialized(self) -> None:
        """Initialize scan state if process_file is called standalone (e.g., in tests)."""
        if not hasattr(self, "_path_index") or self._path_index is None:
            self._path_index = {}
        if not hasattr(self, "_path_index_seen"):
            self._path_index_seen = set()
        if not hasattr(self, "_touch_ids"):
            self._touch_ids = set()
        if not hasattr(self, "_missing_candidates"):
            self._missing_candidates = None
        if not hasattr(self, "_artist_cache"):
            self._artist_cache = {}
        if not hasattr(self, "_pending_artists"):
            self._pending_artists = set()
        if not hasattr(self, "_work_cache"):
            self._work_cache = {}
        if not hasattr(self, "_pending_works"):
            self._pending_works = []
        if not hasattr(self, "_vector_tracks_to_add"):
            self._vector_tracks_to_add = []
        if not hasattr(self, "_last_commit_created"):
            self._last_commit_created = 0
        if not hasattr(self, "_last_commit_moved"):
            self._last_commit_moved = 0

    async def _should_skip_file_stat_first(
        self,
        file_path: Path,
        stats: ScanStats
    ) -> tuple[bool, Optional[os.stat_result]]:
        """Check if file should be skipped based on stat-first optimization.

        Returns:
            Tuple of (should_skip, stat_result)
            - should_skip: True if file should be skipped, False if it needs processing
            - stat_result: os.stat_result if successful, None if stat failed
        """
        # Get file stats
        try:
            stat = file_path.stat()
        except OSError as e:
            logger.warning(f"Could not stat {file_path}: {e}")
            async with self._processing_lock:
                stats.errors += 1
                stats.processed += 1
            return (True, None)  # Skip file

        # Mark path as seen
        # Normalize path to use forward slashes for cross-platform compatibility
        path_str = str(file_path).replace("\\", "/")
        await self._mark_path_seen(path_str)

        # Check if file is in path index
        if path_str not in self._path_index:
            return (False, stat)  # New file, needs processing

        ent = self._path_index[path_str]
        idx_size = ent.get("size")
        idx_mtime = ent.get("mtime")
        lib_id = ent.get("id")

        # Size doesn't match - needs processing
        if idx_size is None or idx_size != stat.st_size:
            # FIX 2: File exists but size changed - update size/mtime without re-creating hierarchy
            if lib_id is not None:
                logger.info(f"File size changed for {path_str}: {idx_size} → {stat.st_size}")
                await self.session.execute(
                    update(LibraryFile)
                    .where(LibraryFile.id == lib_id)
                    .values(size=stat.st_size, mtime=float(stat.st_mtime))
                )
                async with self._processing_lock:
                    stats.skipped += 1
                    stats.processed += 1
                    # Performance tracking
                    if self.perf_metrics:
                        self.perf_metrics.size_changed_files += 1
                        self.perf_metrics.db_queries_update += 1
                return (True, stat)  # Skip file (already updated)
            return (False, stat)  # New file, needs processing

        # EXACT MATCH: size + mtime both match
        if idx_mtime is not None and idx_mtime == stat.st_mtime:
            async with self._processing_lock:
                stats.skipped += 1
                stats.processed += 1
            # TOUCH: enqueue id for batch update of updated_at (last seen this scan)
            if lib_id is not None:
                await self._add_touch_id(lib_id)
            return (True, stat)  # Skip file

        # FIX 1: Legacy row with mtime=None but size matches
        # Just update mtime WITHOUT extracting metadata (HUGE performance win!)
        if idx_mtime is None and lib_id is not None:
            await self.session.execute(
                update(LibraryFile)
                .where(LibraryFile.id == lib_id)
                .values(mtime=float(stat.st_mtime))
            )
            # Also touch updated_at to mark as seen this scan
            await self._add_touch_id(lib_id)
            async with self._processing_lock:
                stats.skipped += 1
                stats.processed += 1
                # Performance tracking
                if self.perf_metrics:
                    self.perf_metrics.metadata_extractions_skipped += 1
                    self.perf_metrics.legacy_files_updated += 1
                    self.perf_metrics.db_queries_update += 1
            logger.debug(f"Updated mtime for legacy file: {path_str}")
            return (True, stat)  # Skip file

        # File needs processing (mtime changed)
        return (False, stat)

    async def _extract_and_parse_metadata(
        self,
        file_path: Path,
        stats: ScanStats
    ) -> Optional[tuple[LibraryMetadata, Optional[int]]]:
        """Extract and parse metadata from audio file.

        Returns:
            Tuple of (LibraryMetadata, bitrate) if successful, None if extraction failed
        """
        # 1. Metadata extraction
        loop = asyncio.get_running_loop()
        audio = await loop.run_in_executor(
            self.executor, self._extract_metadata, file_path
        )

        # Performance tracking
        if self.perf_metrics:
            self.perf_metrics.metadata_extractions += 1

        if not audio:
            async with self._processing_lock:
                stats.skipped += 1
                stats.processed += 1
            return None

        # Parse metadata from audio tags
        (artist_name, album_artist, title, album_title, isrc, release_date, duration, bitrate) = self._parse_metadata_from_audio(audio, file_path)

        # Apply filename fallback if needed
        raw_artist, raw_title = self._apply_filename_fallback(artist_name, title, file_path)

        # 2. CREATE AIR-LOCK METADATA (Normalized immediately)
        meta = LibraryMetadata(
            raw_artist=raw_artist,
            raw_title=raw_title,
            album_artist=album_artist,
            album_title=album_title,
            duration=duration,
            isrc=isrc,
            release_date=release_date,
        )

        return (meta, bitrate)

    async def _handle_moved_file(
        self,
        file_path: Path,
        path_str: str,
        meta: LibraryMetadata,
        stat: os.stat_result,
        stats: ScanStats
    ) -> bool:
        """Check for and handle moved files.

        Returns:
            True if file was moved (and handled), False if it's a new file
        """
        await self._ensure_missing_candidates()
        pid_primary, pid_fallback = self._content_pid(meta.artist, meta.title, file_path)
        candidate = await self._find_move_candidate(pid_primary, pid_fallback, stat.st_size)

        if not candidate:
            return False  # Not a moved file

        # Update LibraryFile with new path
        await self.session.execute(
            update(LibraryFile)
            .where(LibraryFile.id == candidate["lib_id"])
            .values(
                path=path_str,
                size=stat.st_size,
                mtime=float(stat.st_mtime),
            )
        )

        # Update path index (thread-safe)
        await self._update_path_index_for_move(
            candidate["old_path"], path_str, candidate["lib_id"], stat.st_size, stat.st_mtime
        )

        async with self._processing_lock:
            stats.moved += 1
            stats.processed += 1

        return True  # File was moved

    async def _create_new_library_file(
        self,
        file_path: Path,
        meta: LibraryMetadata,
        bitrate: Optional[int],
        stat: os.stat_result,
        stats: ScanStats
    ) -> None:
        """Create new library file with full hierarchy.

        Creates: Artist → Work → Recording → LibraryFile
        Also handles vector indexing and stats updates.
        """
        # Lock database operations to prevent "Session is already flushing" errors
        # Metadata extraction above is still parallel (the slow part)
        async with self._processing_lock:
            # Determine primary artist (for Work)
            is_compilation = meta.album_artist and meta.album_artist.lower() in [
                "various artists",
                "various",
                "va",
            ]

            # Ambiguous Split Detection
            await self._check_ambiguous_artist_split(meta.raw_artist, meta.album_artist)

            # Artist Records (batched: flush once so .id is available)
            primary_artist = await self._get_or_create_artist(meta.artist)
            album_artist_obj = await self._get_or_create_artist(
                meta.album_artist
            )
            await self._flush_pending_artists()

            # Album
            album = None
            if meta.album_title:
                album = await self._get_or_create_album(
                    meta.album_title, album_artist_obj.id, meta.release_date
                )

            # Work & Recording (Parsing/Normalization already done in Meta object)
            work = await self._get_or_create_work(
                meta.work_title, primary_artist.id
            )

            # Multi-Artist Scoring: Link all artists
            await self._link_multi_artists(work, primary_artist, meta.raw_artist, meta.album_artist)

            recording = await self._get_or_create_recording(
                work.id, meta.title, meta.version_type, meta.duration, meta.isrc
            )

            # Calculate file hash (MD5 for deduplication)
            loop = asyncio.get_running_loop()
            file_hash = await loop.run_in_executor(
                self.executor, self._calculate_file_hash, file_path
            )

            # Create LibraryFile (mtime from stat for scan index)
            await self._create_library_file(
                recording, file_path, file_hash, bitrate, mtime=float(stat.st_mtime)
            )

            # Queue for batched vector index update
            buf = getattr(self, "_vector_tracks_to_add", None)
            if buf is not None:
                buf.append((recording.id, meta.artist, meta.title))
                if len(buf) >= self.config.vector_batch_size:
                    self._flush_vector_tracks()
            else:
                self.vector_db.add_track(
                    recording.id, meta.artist, meta.title
                )

            stats.created += 1
            stats.processed += 1

    def _handle_file_error(
        self,
        file_path: Path,
        error: Exception,
        stats: ScanStats,
        context: str = ""
    ) -> None:
        """Centralized error handling for file processing.

        Args:
            file_path: Path to the file that caused the error
            error: The exception that was raised
            stats: Scan statistics to update
            context: Optional context about where the error occurred
        """
        error_type = type(error).__name__

        if isinstance(error, ID3NoHeaderError):
            # ID3NoHeaderError is common for non-MP3 files, just debug log
            logger.debug(f"No ID3 header in {file_path}")
        elif isinstance(error, OSError):
            # File I/O errors (permission denied, file not found, etc.)
            logger.warning(f"File I/O error for {file_path}: {error}")
        elif isinstance(error, IntegrityError):
            # Database integrity error (UNIQUE constraint, foreign key, etc.)
            # This is usually a race condition from parallel processing
            logger.warning(
                f"Database integrity error for {file_path} "
                f"(likely race condition): {error}"
            )
            # NOTE: We do NOT rollback here because:
            # 1. We're using parallel processing with a shared session
            # 2. Rollback would close the transaction for ALL parallel tasks
            # 3. The error is isolated to this file, other files can continue
        else:
            # Unexpected errors - log with full traceback
            context_str = f" ({context})" if context else ""
            logger.error(
                f"Failed to process {file_path}{context_str}: "
                f"{error_type}: {error}",
                exc_info=True
            )

        # Update stats
        stats.errors += 1
        stats.processed += 1

    async def process_file(self, file_path: Path, stats: ScanStats):
        """Extracts metadata from an audio file and upserts it to the database.

        Uses stat-first skip: if path is in path_index with same size and mtime,
        skips metadata extraction and DB write. Otherwise extracts metadata,
        deduplicates, and creates/updates hierarchy and LibraryFile.
        """
        try:
            # Initialize scan state if called standalone (e.g., in tests)
            self._ensure_scan_state_initialized()

            # 0. Stat-first: avoid opening file if unchanged
            should_skip, stat = await self._should_skip_file_stat_first(file_path, stats)
            if should_skip:
                return

            # path_str is used later for move detection
            path_str = str(file_path)

            # 1. Extract and parse metadata
            result = await self._extract_and_parse_metadata(file_path, stats)
            if result is None:
                return  # Metadata extraction failed, already updated stats
            meta, bitrate = result

            # 2. Move detection: check if file was moved to new path
            was_moved = await self._handle_moved_file(file_path, path_str, meta, stat, stats)
            if was_moved:
                return  # File was moved, already updated stats

            # 3. Create new library file with full hierarchy
            await self._create_new_library_file(file_path, meta, bitrate, stat, stats)

        except Exception as e:
            # Use centralized error handler
            self._handle_file_error(file_path, e, stats)

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file for deduplication. Blocking I/O."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash {file_path}: {e}")
            return None
