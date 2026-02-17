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
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False

import mutagen
from loguru import logger
from mutagen.id3 import ID3NoHeaderError
from sqlalchemy import and_, delete, insert, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, InvalidRequestError, MissingGreenlet
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
from airwave.core.config import settings
from airwave.core.normalization import Normalizer
from airwave.core.performance import PerformanceMetrics
from airwave.core.scanner_config import ScannerConfig
from airwave.core.stats import ScanStats
from airwave.core.task_store import TaskStore
from airwave.core.vector_db import VectorDB
from airwave.worker.matcher import Matcher


# MusicBrainz Artist ID: standard UUID format (8-4-4-4-12 hex)
_MBID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _parse_mbid_list(raw: Optional[str]) -> List[str]:
    """Parse raw MBID tag value (single UUID or comma-separated) into list of valid UUIDs."""
    if not raw or not raw.strip():
        return []
    result = []
    for part in raw.split(","):
        s = part.strip()
        if s and _MBID_PATTERN.match(s):
            result.append(s)
    return result


def _extract_mbid_from_tags(tags: Any) -> Tuple[Optional[str], Optional[str]]:
    """Extract MusicBrainz Artist Id and Album Artist Id from Mutagen tags.

    Supports ID3 (TXXX frames) and Vorbis/FLAC (MUSICBRAINZ_* keys).
    Returns (artist_mbid_raw, album_artist_mbid_raw); each may be comma-separated.
    """
    artist_raw: Optional[str] = None
    album_artist_raw: Optional[str] = None
    if tags is None:
        return (None, None)
    # Vorbis / FLAC / OGG
    if hasattr(tags, "get"):
        v_artist = tags.get("MUSICBRAINZ_ARTISTID", [""])
        v_album = tags.get("MUSICBRAINZ_ALBUMARTISTID", [""])
        if v_artist and v_artist[0]:
            artist_raw = (v_artist[0] or "").strip()
        if v_album and v_album[0]:
            album_artist_raw = (v_album[0] or "").strip()
    # ID3 TXXX frames
    if hasattr(tags, "getall"):
        for frame in tags.getall("TXXX") or []:
            desc = getattr(frame, "desc", None)
            text = getattr(frame, "text", None) or []
            val = (text[0] or "").strip() if text else ""
            if not val:
                continue
            if desc == "MusicBrainz Artist Id":
                artist_raw = val
            elif desc == "MusicBrainz Album Artist Id":
                album_artist_raw = val
    return (artist_raw or None, album_artist_raw or None)


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
        artist_mbids: Valid MusicBrainz Artist IDs from track artist tag.
        album_artist_mbids: Valid MusicBrainz Artist IDs from album artist tag.
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
        artist_mbids: Optional[List[str]] = None,
        album_artist_mbids: Optional[List[str]] = None,
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
            artist_mbids: List of valid MusicBrainz Artist IDs for track artist.
            album_artist_mbids: List of valid MusicBrainz Artist IDs for album artist.
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
        self.artist_mbids = artist_mbids or []
        self.album_artist_mbids = album_artist_mbids or []


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

    @staticmethod
    def _count_audio_files_sync(
        root_path: str,
        target_subdirs: Optional[set],
        extensions: Set[str],
    ) -> int:
        """Count audio files under root_path (optionally under target_subdirs only).
        Uses same extension and directory filtering as the main scan. Intended for
        progress total; run in executor to avoid blocking.
        """
        count = 0
        try:
            entries = list(os.scandir(root_path))
        except (OSError, PermissionError):
            return 0
        for entry in entries:
            if entry.is_file():
                if Path(entry.path).suffix.lower() in extensions:
                    count += 1
            elif entry.is_dir():
                dir_norm = str(Path(entry.path).resolve()).replace("\\", "/")
                if target_subdirs is None or any(
                    t == dir_norm or dir_norm.startswith(t + "/") or t.startswith(dir_norm + "/")
                    for t in target_subdirs
                ):
                    count += FileScanner._count_audio_files_sync(
                        entry.path, target_subdirs, extensions
                    )
        return count

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

        # Log hash algorithm being used
        if HAS_BLAKE3:
            logger.info("Using BLAKE3 for file hashing (fast, parallel, cryptographically secure)")
        else:
            logger.warning("BLAKE3 not available, falling back to MD5 for file hashing")

        # Initialize separate ThreadPools for blocking I/O operations
        # Separate executors prevent contention between metadata extraction and file hashing
        self.metadata_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.metadata_workers,
            thread_name_prefix="metadata"
        )
        self.hashing_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.hashing_workers,
            thread_name_prefix="hashing"
        )
        logger.info(
            f"Initialized executors: {self.config.metadata_workers} metadata workers, "
            f"{self.config.hashing_workers} hashing workers"
        )
        # Performance monitoring
        self.perf_metrics: Optional[PerformanceMetrics] = None
        # Concurrency control
        self._processing_lock = asyncio.Lock()  # For thread-safe stats updates
        self._session_lock = asyncio.Lock()  # For commit/rollback synchronization

    # ========== Session Helpers (IntegrityError / Race Condition Handling) ==========

    async def _safe_flush(self, context: str) -> bool:
        """Flush session, handling IntegrityError from race conditions in parallel processing.

        Returns:
            True if flush succeeded, False if IntegrityError occurred and rollback was performed.
        """
        try:
            await self.session.flush()
            return True
        except IntegrityError as e:
            logger.error(
                f"IntegrityError during {context}: {e}"
            )
            await self.session.rollback()
            return False

    async def _safe_commit(self, context: str) -> bool:
        """Commit session, handling IntegrityError from race conditions in parallel processing.

        Returns:
            True if commit succeeded, False if IntegrityError occurred and rollback was performed.
        """
        try:
            await self.session.commit()
            return True
        except IntegrityError as e:
            logger.debug(
                f"IntegrityError during {context} (race condition in parallel processing): {e}"
            )
            await self.session.rollback()
            return False

    # ========== UPSERT Helper Methods (Atomic Database Operations) ==========

    # ============================================================================
    # UPSERT Methods - Database-Native Atomic Operations
    # ============================================================================
    # These methods use SQLite's INSERT...ON CONFLICT syntax to handle entity
    # creation atomically at the database level, eliminating race conditions
    # that were present in the old check-then-insert pattern.
    #
    # Benefits of UPSERT pattern:
    # - Eliminates race conditions: Database handles conflicts atomically
    # - Simpler code: No need for complex flush/rollback/retry logic
    # - Better performance: Fewer round trips, atomic operations
    # - More maintainable: Fewer moving parts, clearer intent
    #
    # Migration notes:
    # - Artists: Use ON CONFLICT DO UPDATE on unique constraint (name)
    # - Works: No unique constraint, so query first then insert with error handling
    # - Recordings: No unique constraint, so query first then insert with error handling
    # - WorkArtist: Use ON CONFLICT DO NOTHING on composite primary key (work_id, artist_id)
    # ============================================================================

    async def _upsert_artist(self, name: str, mbid: Optional[str] = None) -> Artist:
        """Atomically insert or get existing artist using database UPSERT.

        Uses SQLite's INSERT...ON CONFLICT to handle race conditions at the database level.
        This replaces the old _get_or_create_artist() method which used batched inserts
        with manual caching and flush management.

        Args:
            name: Artist name (should be pre-cleaned)
            mbid: Optional MusicBrainz ID

        Returns:
            Artist object with ID populated
        """
        if not name:
            name = "unknown artist"

        # Build UPSERT statement
        stmt = sqlite_insert(Artist).values(
            name=name,
            musicbrainz_id=mbid,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # On conflict with name, update the MBID if it's NULL and we have one
        if mbid:
            stmt = stmt.on_conflict_do_update(
                index_elements=[Artist.name],
                set_=dict(
                    musicbrainz_id=mbid,
                    updated_at=datetime.now(timezone.utc),
                ),
                where=Artist.musicbrainz_id.is_(None),
            )
        else:
            # Just update the timestamp
            stmt = stmt.on_conflict_do_update(
                index_elements=[Artist.name],
                set_=dict(updated_at=datetime.now(timezone.utc)),
            )

        # Execute the UPSERT
        await self.session.execute(stmt)
        await self.session.flush()

        # Query to get the artist (whether it was inserted or already existed)
        stmt_select = select(Artist).where(Artist.name == name)
        result = await self.session.execute(stmt_select)
        artist = result.scalar_one()

        return artist

    async def _upsert_work(self, title: str, artist_id: int) -> Work:
        """Atomically insert or get existing work using database UPSERT.

        Uses query-first-then-insert pattern with IntegrityError handling since Works
        don't have a unique constraint on (title, artist_id). This replaces the old
        _get_or_create_work() method which used batched inserts with manual caching.

        Args:
            title: Work title (should be pre-cleaned)
            artist_id: Primary artist ID

        Returns:
            Work object with ID populated
        """
        # Query first since there's no unique constraint on (title, artist_id)
        stmt = select(Work).where(
            Work.title == title,
            Work.artist_id == artist_id
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Insert new work
        stmt = sqlite_insert(Work).values(
            title=title,
            artist_id=artist_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Since there's no unique constraint on (title, artist_id), we can't use ON CONFLICT
        # We'll just insert and handle IntegrityError if it happens (race condition)
        try:
            await self.session.execute(stmt)
            await self.session.flush()

            # Query to get the work we just created
            stmt_select = select(Work).where(
                Work.title == title,
                Work.artist_id == artist_id
            )
            result = await self.session.execute(stmt_select)
            work = result.scalar_one()
            return work
        except IntegrityError:
            # Another thread created it, query again
            await self.session.rollback()
            stmt = select(Work).where(
                Work.title == title,
                Work.artist_id == artist_id
            )
            result = await self.session.execute(stmt)
            work = result.scalar_one_or_none()
            if not work:
                raise RuntimeError(f"Failed to create or retrieve work: title={title!r}, artist_id={artist_id}")
            return work

    async def _upsert_recording(
        self,
        work_id: int,
        title: str,
        version_type: Optional[str] = None,
        duration: Optional[float] = None,
        isrc: Optional[str] = None,
    ) -> Recording:
        """Atomically insert or get existing recording using database UPSERT.

        Uses query-first-then-insert pattern with IntegrityError handling since Recordings
        don't have a unique constraint on (work_id, title). This replaces the old
        _get_or_create_recording() method which used manual flush/rollback/retry logic.

        Args:
            work_id: Work ID
            title: Recording title (should be pre-cleaned)
            version_type: Optional version type (e.g., "Remix", "Live")
            duration: Optional duration in seconds
            isrc: Optional ISRC code

        Returns:
            Recording object with ID populated
        """
        # Query first since there's no unique constraint on (work_id, title)
        stmt = select(Recording).where(
            Recording.work_id == work_id,
            Recording.title == title
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Insert new recording
        stmt = sqlite_insert(Recording).values(
            work_id=work_id,
            title=title,
            version_type=version_type,
            duration=duration,
            isrc=isrc,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        try:
            await self.session.execute(stmt)
            await self.session.flush()

            # Query to get the recording we just created
            stmt_select = select(Recording).where(
                Recording.work_id == work_id,
                Recording.title == title
            )
            result = await self.session.execute(stmt_select)
            recording = result.scalar_one()
            return recording
        except IntegrityError:
            # Another thread created it, query again
            await self.session.rollback()
            stmt = select(Recording).where(
                Recording.work_id == work_id,
                Recording.title == title
            )
            result = await self.session.execute(stmt)
            recording = result.scalar_one_or_none()
            if not recording:
                raise RuntimeError(f"Failed to create or retrieve recording: work_id={work_id}, title={title!r}")
            return recording

    async def _upsert_work_artist(
        self, work_id: int, artist_id: int, role: str = "Primary"
    ) -> None:
        """Atomically insert work-artist relationship using database UPSERT.

        Uses SQLite's INSERT...ON CONFLICT DO NOTHING to handle duplicates at the
        database level. This replaces the old manual check-then-insert pattern in
        _link_multi_artists() and _link_artist_objects() which was prone to race
        conditions when the same artist appeared multiple times.

        Args:
            work_id: Work ID
            artist_id: Artist ID
            role: Role (e.g., "Primary", "Featured")
        """
        stmt = sqlite_insert(WorkArtist).values(
            work_id=work_id,
            artist_id=artist_id,
            role=role,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # On conflict (duplicate work-artist relationship), do nothing
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[WorkArtist.work_id, WorkArtist.artist_id]
        )

        await self.session.execute(stmt)
        await self.session.flush()

    # ========== Thread-Safe Helper Methods (Phase 1: Race Condition Fixes) ==========

    async def _mark_path_seen(self, path: str) -> None:
        """Thread-safe: Mark path as seen in this scan."""
        async with self._processing_lock:
            self._path_index_seen.add(path)

    async def _add_touch_id(self, file_id: int) -> None:
        """Thread-safe: Add file ID to touch batch and flush if threshold reached.
        Flush acquires _session_lock to serialize with commits."""
        async with self._processing_lock:
            self._touch_ids.add(file_id)
            if len(self._touch_ids) >= self.config.touch_batch_size:
                async with self._session_lock:
                    await self._flush_touch()

    async def _update_path_index_for_move(
        self, old_path: str, new_path: str, file_id: int, size: int, mtime: float
    ) -> None:
        """Thread-safe: Update path index when file is moved.
        
        Paths should already be normalized (resolved, forward slashes, lowercase on Windows).
        """
        async with self._processing_lock:
            # Normalize paths for index update (defensive - paths should already be normalized)
            old_normalized = old_path.replace("\\", "/")
            new_normalized = new_path.replace("\\", "/")
            if sys.platform == "win32":
                old_normalized = old_normalized.lower()
                new_normalized = new_normalized.lower()
                
            self._path_index.pop(old_normalized, None)
            self._path_index[new_normalized] = {
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
            # Folder-level skip: if directory mtime unchanged, skip entire dir (Navidrome optimization)
            # Only applies in incremental mode (full_scan=False); full_scan=True processes all
            stat_dir = None
            resolved_dir = Path(current_path).resolve().as_posix()
            # Normalize to lowercase on Windows for case-insensitive matching
            if sys.platform == "win32":
                dir_path_normalized = resolved_dir.lower()
            else:
                dir_path_normalized = resolved_dir
            if self.config.enable_folder_skip:
                try:
                    stat_dir = await asyncio.get_running_loop().run_in_executor(
                        None, os.stat, current_path
                    )
                except OSError:
                    stat_dir = None
            if (
                self.config.enable_folder_skip
                and not getattr(self, "_full_scan", True)
                and stat_dir is not None
                and getattr(self, "_folder_mtime_cache", None) is not None
            ):
                cached_mtime = self._folder_mtime_cache.get(dir_path_normalized)
                if cached_mtime is not None and stat_dir.st_mtime == cached_mtime:
                    if self.perf_metrics:
                        self.perf_metrics.directories_skipped += 1
                    # Mark paths under this dir as seen so orphan GC won't delete them
                    dir_prefix = dir_path_normalized.rstrip("/") + "/"
                    async with self._processing_lock:
                        for p in list(getattr(self, "_path_index", {}).keys()):
                            if p == dir_path_normalized or p.startswith(dir_prefix):
                                self._path_index_seen.add(p)
                    logger.debug(
                        f"Skipping unchanged directory (folder-level): {current_path}"
                    )
                    return

            # Track directory processing
            if self.perf_metrics:
                self.perf_metrics.directories_processed += 1

            entries = await asyncio.get_running_loop().run_in_executor(
                None, lambda: list(os.scandir(current_path))
            )

            # Update folder cache with current mtime for next scan
            if self.config.enable_folder_skip and stat_dir is not None:
                self._folder_mtime_cache[dir_path_normalized] = stat_dir.st_mtime

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

            # Selective scan: skip file processing when at ancestor of target (not target itself)
            target_subdirs_check = getattr(self, "_target_subdirs", None)
            if target_subdirs_check and files_to_process:
                # We're at an ancestor if: not in targets, but some target is under us
                is_ancestor = (
                    dir_path_normalized not in target_subdirs_check
                    and any(t.startswith(dir_path_normalized.rstrip("/") + "/") for t in target_subdirs_check)
                )
                if is_ancestor:
                    files_to_process = []  # Skip files in this dir, only recurse

            # Process files in this directory concurrently with semaphore
            if files_to_process:
                await self._process_files_with_semaphore(files_to_process, stats, task_id)

            if stats.cancelled:
                return

            # Filter dirs for selective scan (target_subdirs)
            target_subdirs = getattr(self, "_target_subdirs", None)
            if target_subdirs:
                filtered_dirs = []
                for dir_path in dirs_to_process:
                    dir_norm = str(Path(dir_path).resolve()).replace("\\", "/")
                    # Include if dir is in targets, or is a prefix of a target, or is under a target
                    if any(
                        dir_norm == t or dir_norm.startswith(t + "/") or t.startswith(dir_norm + "/")
                        for t in target_subdirs
                    ):
                        filtered_dirs.append(dir_path)
                dirs_to_process = filtered_dirs

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
                            async with self._session_lock:
                                await self._flush_touch()  # Flush pending touch updates
                                await self._safe_commit("periodic commit")
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
        self,
        root_path: str,
        task_id: Optional[str] = None,
        target_subdirs: Optional[List[str]] = None,
        full_scan: bool = True,
    ) -> ScanStats:
        """Recursively scans a directory for audio files and syncs them to DB.

        Args:
            root_path: Root directory to scan.
            task_id: Optional task ID for progress tracking.
            target_subdirs: Optional list of subpaths (relative to root_path) to scan.
                If provided, only these paths and their descendants are scanned.
                E.g. ["2024", "Albums/New"] scans only root/2024 and root/Albums/New.
            full_scan: If True (default), scan all files. If False (incremental),
                use folder mtime cache to skip unchanged directories.

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
        # Normalize paths consistently: resolve and use forward slashes
        # On Windows, also normalize to lowercase for case-insensitive matching
        stmt = select(LibraryFile.id, LibraryFile.path, LibraryFile.size, LibraryFile.mtime)
        result = await self.session.execute(stmt)
        path_index: Dict[str, Dict[str, Any]] = {}
        for row in result.all():
            # Normalize path consistently: resolve to absolute, use forward slashes
            # On Windows, also normalize to lowercase for case-insensitive matching
            # This MUST match the normalization used when storing (line ~1423) and checking (line ~1502)
            try:
                # Resolve to absolute path (same as when storing/checking)
                # This handles symlinks, relative paths, and ensures consistent format
                resolved = Path(row.path).resolve().as_posix()
            except (OSError, ValueError):
                # If path doesn't exist or can't be resolved, normalize as-is
                # This handles legacy paths or deleted files gracefully
                resolved = row.path.replace("\\", "/")
            
            # On Windows, normalize to lowercase for case-insensitive matching
            # This ensures paths match regardless of filesystem-reported casing
            if sys.platform == "win32":
                normalized_path = resolved.lower()
            else:
                normalized_path = resolved
                
            path_index[normalized_path] = {"id": row.id, "size": row.size, "mtime": row.mtime}
        self._path_index = path_index
        self._path_index_seen: set = set()
        self._touch_ids: set = set()
        self._missing_candidates: Optional[List[Dict[str, Any]]] = None
        self._vector_tracks_to_add: List[Tuple[int, str, str]] = []
        self._last_commit_created: int = 0  # Track created count at last commit
        self._last_commit_moved: int = 0    # Track moved count at last commit
        logger.info(f"Loaded path index: {len(path_index)} files")

        # Load folder mtime cache for folder-level skip optimization
        # On full scan, ignore cache (will rebuild it during scan)
        if full_scan:
            self._folder_mtime_cache: Dict[str, float] = {}
        else:
            self._folder_mtime_cache: Dict[str, float] = self._load_folder_cache(root_path)
        self._full_scan: bool = full_scan

        # Resolve target subdirs to absolute paths for selective scan
        self._target_subdirs: Optional[set] = None
        if target_subdirs:
            root_resolved = str(Path(root_path).resolve()).replace("\\", "/")
            self._target_subdirs = {
                str((Path(root_path) / t).resolve()).replace("\\", "/")
                for t in target_subdirs
            }
            # Filter to paths under root
            self._target_subdirs = {
                p for p in self._target_subdirs
                if p == root_resolved or p.startswith(root_resolved + "/")
            }
            if self._target_subdirs:
                logger.info(f"Selective scan: targeting {len(self._target_subdirs)} subdirs")

        # Optional: count files for accurate progress (same extensions + target_subdirs)
        if task_id:
            loop = asyncio.get_running_loop()
            expected_count = await loop.run_in_executor(
                None,
                lambda: FileScanner._count_audio_files_sync(
                    root_path,
                    getattr(self, "_target_subdirs", None),
                    self.SUPPORTED_EXTENSIONS,
                ),
            )
            if expected_count > 0:
                self.task_store.update_total(
                    task_id, expected_count, f"Scanning {expected_count} files..."
                )
                logger.info(f"Expected file count for progress: {expected_count}")

        # Recursive Scan using scandir with parallel file processing
        await self._process_recursive(root_path, stats, task_id)

        # Check if scan was cancelled
        if task_id and self.task_store.is_cancelled(task_id):
            # Flush any pending changes before cancelling
            await self._flush_touch()
            self._flush_vector_tracks()
            await self._safe_commit("final commit (cancelled)")

            self.task_store.mark_cancelled(task_id)
            logger.warning(f"Scan cancelled after processing {stats.processed} files")
            return stats

        await self._flush_touch()
        self._flush_vector_tracks()
        await self._safe_commit("final commit")

        # Persist folder mtime cache for next scan
        self._save_folder_cache(root_path)

        # Post-scan orphan GC: remove LibraryFiles no longer on disk
        gc_deleted = await self._finalize_scan_orphan_gc()
        if gc_deleted > 0:
            logger.info(f"Orphan GC: removed {gc_deleted} LibraryFile rows (files no longer on disk)")

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

    def _folder_cache_path(self, root_path: str) -> Path:
        """Path to folder mtime cache file, scoped per library root."""
        resolved = Path(root_path).resolve().as_posix()
        # Normalize to lowercase on Windows for case-insensitive matching
        if sys.platform == "win32":
            normalized = resolved.lower()
        else:
            normalized = resolved
        key = hashlib.md5(normalized.encode()).hexdigest()[:16]
        return Path(settings.DATA_DIR) / "scan_folder_cache" / f"{key}.json"

    def _load_folder_cache(self, root_path: str) -> Dict[str, float]:
        """Load folder mtime cache from disk for folder-level skip optimization.
        
        Normalizes paths to lowercase on Windows for case-insensitive matching.
        Handles legacy cache entries gracefully.
        """
        path = self._folder_cache_path(root_path)
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                data = json.load(f)
            cache = dict(data) if isinstance(data, dict) else {}
            # Normalize cache keys to lowercase on Windows (handles legacy entries)
            if sys.platform == "win32":
                normalized_cache = {}
                for key, value in cache.items():
                    try:
                        normalized_key = Path(key).resolve().as_posix().lower()
                    except (OSError, ValueError):
                        normalized_key = key.replace("\\", "/").lower()
                    normalized_cache[normalized_key] = value
                return normalized_cache
            return cache
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Could not load folder cache from {path}: {e}")
            return {}

    def _save_folder_cache(self, root_path: str) -> None:
        """Persist folder mtime cache to disk for next scan."""
        cache = getattr(self, "_folder_mtime_cache", None)
        if not cache:
            return
        path = self._folder_cache_path(root_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w") as f:
                json.dump(cache, f, indent=0)
        except OSError as e:
            logger.warning(f"Could not save folder cache to {path}: {e}")

    async def _finalize_scan_orphan_gc(self) -> int:
        """Remove LibraryFile rows for paths no longer seen on disk (orphan GC).
        Streams rows instead of loading all into memory for large libraries."""
        path_index_seen = getattr(self, "_path_index_seen", None)
        if not path_index_seen:
            return 0
        stmt = select(LibraryFile.id, LibraryFile.path)
        ids_to_delete: List[int] = []
        async with self._session_lock:
            result = await self.session.stream(stmt)
            async for row in result:
                # Normalize path for comparison (same as skip check)
                try:
                    normalized_db_path = Path(row.path).resolve().as_posix()
                except (OSError, ValueError):
                    normalized_db_path = row.path.replace("\\", "/")
                if sys.platform == "win32":
                    normalized_db_path = normalized_db_path.lower()
                    
                if normalized_db_path not in path_index_seen:
                    ids_to_delete.append(row.id)
            await result.close()
        if not ids_to_delete:
            return 0
        # Delete in batches to avoid huge IN clause
        batch_size = 500
        deleted = 0
        async with self._session_lock:
            for i in range(0, len(ids_to_delete), batch_size):
                batch = ids_to_delete[i : i + batch_size]
                await self.session.execute(
                    delete(LibraryFile).where(LibraryFile.id.in_(batch))
                )
                deleted += len(batch)
            if deleted > 0:
                await self._safe_commit("orphan cleanup commit")
        return deleted

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
            # Caller (e.g. _handle_moved_file) holds _session_lock
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
            if not await self._safe_flush("album flush"):
                # Flush failed (race condition), re-query to get the album created by another thread
                stmt = select(Album).where(
                    Album.title == clean_album_title,
                    Album.artist_id == artist_id,
                )
                res = await self.session.execute(stmt)
                album = res.scalar_one_or_none()
                if not album:
                    raise RuntimeError(
                        f"Failed to create or retrieve album: title={clean_album_title!r}, "
                        f"artist_id={artist_id}. This indicates a database consistency issue."
                    )

        return album

    def _parse_metadata_from_audio(
        self, audio: Any, file_path: Path
    ) -> Tuple[
        str, str, str, str, Optional[str], Optional[datetime], Optional[float], Optional[int],
        Optional[str], Optional[str],
    ]:
        """Parse metadata from audio tags.

        Args:
            audio: Mutagen audio object with metadata tags.
            file_path: Path to the audio file (for fallback parsing).

        Returns:
            Tuple of (artist_name, album_artist, title, album_title, isrc, release_date,
            duration, bitrate, artist_mbid_raw, album_artist_mbid_raw).
        """
        # Extract basic metadata
        artist_name = audio.get("artist", [""])[0]
        album_artist = audio.get("albumartist", [""])[0]
        title = audio.get("title", [""])[0]
        album_title = audio.get("album", [""])[0]
        isrc = audio.get("isrc", [""])[0] or None
        date_str = audio.get("date", [""])[0] or None

        # MusicBrainz Artist IDs (ID3 TXXX or Vorbis MUSICBRAINZ_*)
        artist_mbid_raw, album_artist_mbid_raw = _extract_mbid_from_tags(
            getattr(audio, "tags", None)
        )

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

        return (
            artist_name, album_artist, title, album_title,
            isrc, release_date, duration, bitrate,
            artist_mbid_raw, album_artist_mbid_raw,
        )

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

        logger.debug(f"_link_multi_artists: work_id={work.id}, unique_targets={unique_targets}")

        for a_clean in unique_targets:
            # Use UPSERT to atomically get or create artist
            a_obj = await self._upsert_artist(a_clean)

            # Determine role
            role = "Primary" if a_obj.id == primary_artist.id else "Featured"

            # Use UPSERT to atomically insert work-artist link (ignores duplicates)
            await self._upsert_work_artist(work.id, a_obj.id, role)

    async def _link_artist_objects(
        self, work: Work, primary_artist: Artist, artist_objs: List[Artist]
    ) -> None:
        """Link a list of artist objects to a work (e.g. from MBID resolution)."""
        for a_obj in artist_objs:
            # Determine role
            role = "Primary" if a_obj.id == primary_artist.id else "Featured"

            # Use UPSERT to atomically insert work-artist link (ignores duplicates)
            await self._upsert_work_artist(work.id, a_obj.id, role)

    async def _create_library_file(
        self,
        recording: Recording,
        file_path: Path,
        file_hash: Optional[str],
        bitrate: Optional[int],
        mtime: Optional[float] = None,
    ) -> LibraryFile:
        """Create and persist a LibraryFile record.

        Args:
            recording: Recording object to link the file to.
            file_path: Path to the audio file.
            file_hash: BLAKE3/MD5 hash of the file (None if hashing failed).
            bitrate: Bitrate of the audio file.
            mtime: Optional filesystem mtime (st_mtime) for scan index.

        Returns:
            The created LibraryFile object.

        Raises:
            OSError: If the file cannot be stat'd (e.g. deleted between stat and create).
            RuntimeError: If LibraryFile not found after IntegrityError re-query (should not occur).
        """
        try:
            st = file_path.stat()
        except OSError as e:
            logger.warning(f"File gone or inaccessible when creating LibraryFile {file_path}: {e}")
            raise
        # Normalize path consistently: resolve to absolute, use forward slashes
        # On Windows, also normalize to lowercase for case-insensitive matching
        # This ensures paths match during skip checks
        resolved_path = file_path.resolve().as_posix()
        if sys.platform == "win32":
            normalized_path = resolved_path.lower()
        else:
            normalized_path = resolved_path
        
        new_file = LibraryFile(
            recording_id=recording.id,
            path=normalized_path,
            size=st.st_size,
            mtime=(mtime if mtime is not None else float(st.st_mtime)),
            format=file_path.suffix.replace(".", ""),
            file_hash=file_hash,
            bitrate=bitrate,
        )
        self.session.add(new_file)
        if not await self._safe_flush("library file flush"):
            stmt = select(LibraryFile).where(LibraryFile.path == normalized_path)
            res = await self.session.execute(stmt)
            new_file = res.scalar_one_or_none()
            if new_file is None:
                raise RuntimeError(
                    f"LibraryFile not found after IntegrityError for path {file_path}"
                )
        
        # Update path_index so subsequent checks can find this file
        # This prevents files created during parallel processing from being detected as "new" again
        if hasattr(self, "_path_index"):
            # Ensure we have an ID before updating path_index
            if new_file.id is None:
                # If ID is None, we need to flush again or refresh
                await self.session.flush()
                if new_file.id is None:
                    logger.warning(
                        f"LibraryFile created but ID is None for path: {normalized_path}"
                    )
            if new_file.id is not None:
                self._path_index[normalized_path] = {
                    "id": new_file.id,
                    "size": new_file.size,
                    "mtime": new_file.mtime,
                }
                logger.debug(
                    f"Added to path_index: {normalized_path} (id: {new_file.id})"
                )
            else:
                logger.warning(
                    f"Could not add to path_index - file has no ID: {normalized_path}"
                )
        
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
        # Normalize path consistently: resolve to absolute, use forward slashes
        # On Windows, also normalize to lowercase for case-insensitive matching
        try:
            resolved_path = file_path.resolve().as_posix()
        except (OSError, ValueError):
            # If path can't be resolved (e.g., deleted), use as-is
            resolved_path = str(file_path).replace("\\", "/")
        
        if sys.platform == "win32":
            path_str = resolved_path.lower()
        else:
            path_str = resolved_path
            
        await self._mark_path_seen(path_str)

        # Check if file is in path index
        if path_str not in self._path_index:
            # Debug logging for path mismatches (can be removed after fixing)
            if len(self._path_index) > 0:
                # Check if a similar path exists (case-insensitive on Windows)
                if sys.platform == "win32":
                    similar_paths = [
                        p for p in self._path_index.keys()
                        if p.lower() == path_str.lower()
                    ]
                else:
                    similar_paths = [
                        p for p in self._path_index.keys()
                        if p == path_str
                    ]
                if similar_paths:
                    logger.warning(
                        f"Path mismatch detected (case?): checking '{path_str}', "
                        f"found similar '{similar_paths[0]}' in index"
                    )
            
            # CRITICAL DEBUG: Check if file actually exists in database
            # This helps identify if files are missing from path_index but exist in DB
            # Limit to first 20 checks to avoid performance impact
            if not hasattr(self, "_db_check_count"):
                self._db_check_count = 0
            
            if self._db_check_count < 20:
                self._db_check_count += 1
                # We need to normalize database paths the same way as path_index loading
                async with self._session_lock:
                    # Query all files and normalize their paths to match path_str
                    stmt = select(LibraryFile.id, LibraryFile.path, LibraryFile.size, LibraryFile.mtime)
                    res = await self.session.execute(stmt)
                    found_match = False
                    for row in res.all():
                        # Normalize database path the same way as path_index loading
                        try:
                            db_resolved = Path(row.path).resolve().as_posix()
                        except (OSError, ValueError):
                            db_resolved = row.path.replace("\\", "/")
                        
                        if sys.platform == "win32":
                            db_normalized = db_resolved.lower()
                        else:
                            db_normalized = db_resolved
                        
                        # If normalized paths match, file exists in DB but wasn't in path_index
                        if db_normalized == path_str:
                            logger.warning(
                                f"BUG: File exists in database but not in path_index! "
                                f"Path: {path_str}, DB ID: {row.id}, "
                                f"DB Path (raw): {row.path}, "
                                f"Size: {row.size}, Mtime: {row.mtime}"
                            )
                            # Add to path_index immediately to prevent duplicate creation
                            self._path_index[path_str] = {
                                "id": row.id,
                                "size": row.size,
                                "mtime": row.mtime,
                            }
                            # File exists, skip processing
                            async with self._processing_lock:
                                stats.skipped += 1
                                stats.processed += 1
                            await self._add_touch_id(row.id)
                            found_match = True
                            return (True, stat)  # Skip file
                    
                    if not found_match:
                        logger.debug(
                            f"File not in path_index and not found in database (check #{self._db_check_count}): {path_str}"
                        )
            
            # Debug: Log which files are detected as new
            logger.debug(
                f"File not in path_index (will be created): {path_str} "
                f"(path_index size: {len(self._path_index)})"
            )
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
                # Update path_index to reflect the new size and mtime
                if path_str in self._path_index:
                    self._path_index[path_str]["size"] = stat.st_size
                    self._path_index[path_str]["mtime"] = float(stat.st_mtime)
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
            # Update path_index to reflect the new mtime
            if path_str in self._path_index:
                self._path_index[path_str]["mtime"] = float(stat.st_mtime)
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
        # 1. Metadata extraction (using dedicated metadata executor)
        loop = asyncio.get_running_loop()
        t_start = time.time()
        audio = await loop.run_in_executor(
            self.metadata_executor, self._extract_metadata, file_path
        )
        t_metadata = time.time() - t_start

        # Performance tracking
        if self.perf_metrics:
            self.perf_metrics.metadata_extractions += 1
            self.perf_metrics.time_metadata_extraction += t_metadata

        if not audio:
            async with self._processing_lock:
                stats.skipped += 1
                stats.processed += 1
            return None

        # Parse metadata from audio tags
        (
            artist_name, album_artist, title, album_title,
            isrc, release_date, duration, bitrate,
            artist_mbid_raw, album_artist_mbid_raw,
        ) = self._parse_metadata_from_audio(audio, file_path)

        # Apply filename fallback if needed
        raw_artist, raw_title = self._apply_filename_fallback(artist_name, title, file_path)

        # Normalize MBID strings to list of valid UUIDs
        artist_mbids = _parse_mbid_list(artist_mbid_raw)
        album_artist_mbids = _parse_mbid_list(album_artist_mbid_raw)

        # 2. CREATE AIR-LOCK METADATA (Normalized immediately)
        meta = LibraryMetadata(
            raw_artist=raw_artist,
            raw_title=raw_title,
            album_artist=album_artist,
            album_title=album_title,
            duration=duration,
            isrc=isrc,
            release_date=release_date,
            artist_mbids=artist_mbids,
            album_artist_mbids=album_artist_mbids,
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
        # Load missing candidates (session op)
        await self._ensure_missing_candidates()

        # Find candidate (in-memory, uses _processing_lock)
        pid_primary, pid_fallback = self._content_pid(meta.artist, meta.title, file_path)
        candidate = await self._find_move_candidate(pid_primary, pid_fallback, stat.st_size)

        if not candidate:
            return False  # Not a moved file

        # Update LibraryFile with new path (session op) - serialize with other session ops
        # Normalize path consistently with _create_library_file (lowercase on Windows)
        normalized_path = path_str.lower() if sys.platform == "win32" else path_str
        async with self._session_lock:
            await self.session.execute(
                update(LibraryFile)
                .where(LibraryFile.id == candidate["lib_id"])
                .values(
                    path=normalized_path,
                    size=stat.st_size,
                    mtime=float(stat.st_mtime),
                )
            )

        # Update path index (thread-safe)
        await self._update_path_index_for_move(
            candidate["old_path"], normalized_path, candidate["lib_id"], stat.st_size, stat.st_mtime
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
        # Serialize database operations to prevent race conditions in parallel processing
        # This ensures artist/work/recording creation is atomic and prevents IntegrityError cascades
        async with self._session_lock:
            t_db_start = time.time()  # Start timer AFTER acquiring lock

            # Calculate file hash (using dedicated hashing executor)
            loop = asyncio.get_running_loop()
            t_hash_start = time.time()
            file_hash = await loop.run_in_executor(
                self.hashing_executor, self._calculate_file_hash, file_path
            )
            t_hash = time.time() - t_hash_start
            if self.perf_metrics:
                self.perf_metrics.time_file_hashing += t_hash

            # Determine primary artist (for Work)
            is_compilation = meta.album_artist and meta.album_artist.lower() in [
                "various artists",
                "various",
                "va",
            ]

            # Ambiguous Split Detection
            await self._check_ambiguous_artist_split(meta.raw_artist, meta.album_artist)

            # Resolve primary artist(s) and album artist by MBID when present
            artist_objs_from_mbid: List[Artist] = []
            if meta.artist_mbids:
                split_names = [
                    Normalizer.clean_artist(a)
                    for a in Normalizer.split_artists(meta.raw_artist or meta.artist)
                ]
                for i, mbid in enumerate(meta.artist_mbids):
                    name = split_names[i] if i < len(split_names) else meta.artist
                    # Use UPSERT to atomically get or create artist
                    a_obj = await self._upsert_artist(name or meta.artist, mbid=mbid)
                    artist_objs_from_mbid.append(a_obj)
                primary_artist = artist_objs_from_mbid[0]
            else:
                # Use UPSERT to atomically get or create artist
                primary_artist = await self._upsert_artist(meta.artist)

            if meta.album_artist_mbids:
                # Use UPSERT to atomically get or create artist
                album_artist_obj = await self._upsert_artist(
                    meta.album_artist, mbid=meta.album_artist_mbids[0]
                )
            else:
                # Use UPSERT to atomically get or create artist
                album_artist_obj = await self._upsert_artist(meta.album_artist)

            # Album
            album = None
            if meta.album_title:
                album = await self._get_or_create_album(
                    meta.album_title, album_artist_obj.id, meta.release_date
                )

            # Work & Recording (Parsing/Normalization already done in Meta object)
            # Use UPSERT to atomically get or create work
            work = await self._upsert_work(meta.work_title, primary_artist.id)

            # Multi-Artist: link MBID-resolved list or name-split list
            if artist_objs_from_mbid:
                await self._link_artist_objects(work, primary_artist, artist_objs_from_mbid)
            else:
                await self._link_multi_artists(
                    work, primary_artist, meta.raw_artist, meta.album_artist
                )

            # Use UPSERT to atomically get or create recording
            recording = await self._upsert_recording(
                work.id, meta.title, meta.version_type, meta.duration, meta.isrc
            )

            # Create LibraryFile (mtime from stat for scan index)
            await self._create_library_file(
                recording, file_path, file_hash, bitrate, mtime=float(stat.st_mtime)
            )

            # Store recording ID for vector indexing (outside lock)
            recording_id = recording.id

        # Track database operation time (session lock released)
        t_db = time.time() - t_db_start
        if self.perf_metrics:
            self.perf_metrics.time_database_ops += t_db

        # Vector indexing (outside session lock for better parallelism).
        # Only increment stats on full success; if this raises, process_file's except
        # will call _handle_file_error (errors += 1, processed += 1) - never double-count.
        try:
            t_vector_start = time.time()
            buf = getattr(self, "_vector_tracks_to_add", None)
            if buf is not None:
                buf.append((recording_id, meta.artist, meta.title))
                if len(buf) >= self.config.vector_batch_size:
                    self._flush_vector_tracks()
            else:
                self.vector_db.add_track(
                    recording_id, meta.artist, meta.title
                )
            t_vector = time.time() - t_vector_start
            if self.perf_metrics:
                self.perf_metrics.time_vector_indexing += t_vector

            stats.created += 1
            stats.processed += 1
        except Exception:
            # Re-raise so process_file's handler can update errors/processed once.
            # Do NOT increment created/processed here - the file creation was not fully successful.
            raise

    async def _handle_file_error(
        self,
        file_path: Path,
        error: Exception,
        stats: ScanStats,
        context: str = ""
    ) -> None:
        """Centralized error handling for file processing.

        This method handles errors that occur during file processing, with special
        handling for IntegrityError to prevent session state issues in parallel processing.

        Session State Management:
            When an IntegrityError occurs (e.g., UNIQUE constraint violation from race
            conditions in parallel processing), SQLAlchemy automatically rolls back the
            transaction, putting the session in 'prepared' state. This prevents any
            further SQL operations from being executed within the same transaction.

            In parallel processing scenarios, this would cause all other concurrent tasks
            to fail with "This session is in 'prepared' state; no further SQL can be
            emitted within this transaction."

            To prevent this, we explicitly call session.rollback() after IntegrityError
            to clear the error state and allow other parallel tasks to continue using
            the session.

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
            # This is expected in parallel processing when multiple files try to create
            # the same artist/work/recording. The data is already in DB from another task.
            logger.debug(
                f"IntegrityError for {file_path} (race condition in parallel processing): {error}"
            )
            await self._rollback_session_for_error(file_path, error_type, "IntegrityError")
        elif isinstance(error, InvalidRequestError) and "prepared" in str(error).lower():
            # InvalidRequestError: "session is in 'prepared' state" - typically a
            # cascade from IntegrityError (or similar) in another parallel task.
            # SQLAlchemy auto-rollback leaves session in prepared state; we must
            # rollback to allow other parallel tasks to continue.
            logger.debug(
                f"Session prepared state for {file_path} (cascade from parallel task): {error}"
            )
            await self._rollback_session_for_error(file_path, error_type, "InvalidRequestError")
        elif isinstance(error, MissingGreenlet):
            # Async session used from wrong greenlet/task context.
            # This is expected in parallel processing when session state is corrupted
            # by errors in other tasks. Don't try to rollback (will cause another error).
            logger.debug(
                f"MissingGreenlet for {file_path} (session state issue from parallel processing): {error}"
            )
            # Don't call _rollback_session_for_error - it will just cause another MissingGreenlet
            # The session will be reset on the next commit
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

    async def _rollback_session_for_error(
        self, file_path: Path, error_type: str, label: str
    ) -> None:
        """Rollback session after IntegrityError or InvalidRequestError (prepared state).

        Call this to clear the session error state so other parallel tasks can continue.
        Uses _session_lock to avoid calling rollback() while commit() is in progress.

        Note: MissingGreenlet errors during rollback are expected in parallel processing
        when the session is accessed from different async contexts. These are logged but
        not treated as fatal errors since the session state will be reset on next commit.
        """
        async with self._session_lock:
            try:
                await self.session.rollback()
                logger.debug(f"Session rolled back after {label}")
            except MissingGreenlet as greenlet_error:
                # Expected in parallel processing - session accessed from different greenlet
                # The session will be reset on next commit, so this is not fatal
                logger.debug(
                    f"MissingGreenlet during rollback (expected in parallel processing): "
                    f"{greenlet_error}"
                )
            except Exception as rollback_error:
                logger.error(f"Failed to rollback session: {rollback_error}")

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

            # path_str is used later for move detection - normalize consistently
            try:
                path_str = file_path.resolve().as_posix()
            except (OSError, ValueError):
                path_str = str(file_path).replace("\\", "/")

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
            await self._handle_file_error(file_path, e, stats)

    def _calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """Calculate file hash for deduplication. Blocking I/O.

        Uses BLAKE3 (fast, parallel, cryptographically secure) if available,
        falls back to MD5 if not. Uses 1MB chunks for optimal performance.

        Returns:
            Hex digest string, or None if hashing failed (e.g. file inaccessible).
        """
        # Use BLAKE3 if available (8-25x faster than MD5)
        if HAS_BLAKE3:
            hasher = blake3.blake3()
        else:
            hasher = hashlib.md5()

        try:
            with open(file_path, "rb") as f:
                # Use 1MB chunks for optimal performance (was 4KB)
                # Larger chunks = fewer system calls = better throughput
                for chunk in iter(lambda: f.read(1048576), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash {file_path}: {e}")
            return None

    def cleanup(self):
        """Clean up resources (thread pools).

        Call this when done with the scanner to ensure proper cleanup.
        """
        if hasattr(self, 'metadata_executor'):
            self.metadata_executor.shutdown(wait=True)
        if hasattr(self, 'hashing_executor'):
            self.hashing_executor.shutdown(wait=True)
        logger.debug("Scanner executors shut down")
