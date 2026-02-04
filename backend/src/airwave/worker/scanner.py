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
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

import mutagen
from loguru import logger
from mutagen.id3 import ID3NoHeaderError
from sqlalchemy import select
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
from airwave.core.stats import ScanStats
from airwave.core.task_store import TaskStore
from airwave.core.vector_db import VectorDB
from airwave.worker.matcher import Matcher


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
        executor: Thread pool executor for parallel metadata extraction.
        SUPPORTED_EXTENSIONS: Set of supported audio file extensions.
    """

    SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".m4a", ".wav", ".ogg"}

    def __init__(self, session: AsyncSession):
        self.session = session
        self.matcher = Matcher(session)
        # Initialize ThreadPool for blocking I/O (mutagen)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def _extract_metadata(self, file_path: Path):
        """Blocking metadata extraction to be run in thread."""
        try:
            return mutagen.File(file_path, easy=True)
        except Exception as e:
            logger.warning(f"Metadata extraction failed for {file_path}: {e}")
            return None

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
                TaskStore.complete_task(
                    task_id, success=False, error="Directory not found"
                )
            # Return empty stats with error counted
            error_stats = ScanStats()
            error_stats.errors = 1
            return error_stats

        # Count total files first for progress tracking (ScanDir is faster)
        logger.info(f"Counting files in {root_path}...")
        total_files = 0

        # Helper to count recursively using scandir
        def count_recursive(path):
            count = 0
            try:
                with os.scandir(path) as it:
                    for entry in it:
                        if entry.is_dir():
                            count += count_recursive(entry.path)
                        elif (
                            entry.is_file()
                            and Path(entry.name).suffix.lower()
                            in self.SUPPORTED_EXTENSIONS
                        ):
                            count += 1
            except PermissionError:
                logger.warning(
                    f"Permission denied while counting files in: {path}"
                )
                pass
            return count

        total_files = await asyncio.get_running_loop().run_in_executor(
            None, count_recursive, root_path
        )

        if task_id:
            TaskStore.update_total(
                task_id, total_files, f"Starting scan... ({total_files} files)"
            )
            logger.info(f"Updated task {task_id} with {total_files} files")

        stats = ScanStats()

        logger.info(f"Starting scan of {root_path}... ({total_files} files)")

        # Load cache for matcher optimization
        if not hasattr(self.matcher, "_vector_db"):
            self.matcher._vector_db = VectorDB()

        # Recursive Scan using scandir
        async def process_recursive(current_path):
            try:
                entries = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: list(os.scandir(current_path))
                )

                for entry in entries:
                    if entry.is_dir():
                        await process_recursive(entry.path)
                    elif entry.is_file():
                        p = Path(entry.path)
                        if p.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                            try:
                                await self.process_file(p, stats)
                            except Exception as e:
                                logger.warning(
                                    f"Failed to process {entry.name}: {e}"
                                )
                                stats.errors += 1

                            stats.processed += 1

                            if task_id and (
                                stats.processed % 10 == 0
                                or stats.processed == total_files
                            ):
                                TaskStore.update_progress(
                                    task_id,
                                    stats.processed,
                                    f"Scanned {entry.name} ({stats.created} new)",
                                )

                            if stats.processed % 100 == 0:
                                await self.session.commit()
            except PermissionError:
                logger.warning(f"Permission denied: {current_path}")
            except Exception as e:
                logger.error(f"Error scanning directory {current_path}: {e}")

        await process_recursive(root_path)

        await self.session.commit()

        if task_id:
            TaskStore.complete_task(task_id, success=True)
            logger.success(f"Task {task_id} completed: {stats}")

        return stats

    async def _get_or_create_artist(self, clean_name: str) -> Artist:
        """Get or create artist using pre-cleaned name."""
        if not clean_name:
            clean_name = "unknown artist"

        stmt = select(Artist).where(Artist.name == clean_name)
        res = await self.session.execute(stmt)
        artist = res.scalar_one_or_none()

        if not artist:
            artist = Artist(name=clean_name)
            self.session.add(artist)
            await self.session.flush()

        return artist

    async def _get_or_create_work(
        self, clean_title: str, artist_id: int
    ) -> Work:
        """Get or create work using pre-cleaned title."""
        stmt = select(Work).where(
            Work.title == clean_title, Work.artist_id == artist_id
        )
        res = await self.session.execute(stmt)
        work = res.scalar_one_or_none()

        if not work:
            work = Work(title=clean_title, artist_id=artist_id)
            self.session.add(work)
            await self.session.flush()

        return work

    async def _get_or_create_recording(
        self,
        work_id: int,
        clean_title: str,
        version_type: str,
        duration: float = None,
        isrc: str = None,
    ) -> Recording:
        """Get or create recording using pre-cleaned title."""
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
        """Get or create an album using pre-cleaned title."""
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
        self, work: Work, primary_artist: Artist, raw_artist: str, album_artist: str
    ) -> None:
        """Link all artists (primary + featured) to the work.

        Args:
            work: Work object to link artists to.
            primary_artist: Primary artist object.
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
        self, recording: Recording, file_path: Path, file_hash: str, bitrate: Optional[int]
    ) -> LibraryFile:
        """Create and persist a LibraryFile record.

        Args:
            recording: Recording object to link the file to.
            file_path: Path to the audio file.
            file_hash: MD5 hash of the file.
            bitrate: Bitrate of the audio file.

        Returns:
            The created LibraryFile object.
        """
        new_file = LibraryFile(
            recording_id=recording.id,
            path=str(file_path),
            size=file_path.stat().st_size,
            format=file_path.suffix.replace(".", ""),
            file_hash=file_hash,
            bitrate=bitrate,
        )
        self.session.add(new_file)
        await self.session.flush()
        return new_file

    async def process_file(self, file_path: Path, stats: ScanStats):
        """Extracts metadata from an audio file and upserts it to the database.

        This method handles:
        1. ID3/Metadata extraction via mutagen.
        2. Creation of normalized 'Air-lock' metadata.
        3. Deduplication against existing LibraryFile records.
        4. Hierarchy creation (Artist -> Album -> Work -> Recording).
        5. File hashing for integrity.

        Args:
            file_path: Absolute path to the audio file.
            stats: ScanStats object to track processing statistics.

        Raises:
            Exception: If file reading fails (unless it's a simple no-header error).
        """
        try:
            # 1. Metadata extraction
            loop = asyncio.get_running_loop()
            audio = await loop.run_in_executor(
                self.executor, self._extract_metadata, file_path
            )

            if not audio:
                stats.skipped += 1
                return

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

            # 3. Check if File exists
            stmt = select(LibraryFile).where(LibraryFile.path == str(file_path))
            result = await self.session.execute(stmt)
            existing_file = result.scalar_one_or_none()

            if existing_file:
                stats.skipped += 1
                return

            # 4. Create Hierarchy using AIR-LOCK CLEANED DATA
            # Determine primary artist (for Work)
            is_compilation = album_artist and album_artist.lower() in [
                "various artists",
                "various",
                "va",
            ]

            # Ambiguous Split Detection
            await self._check_ambiguous_artist_split(meta.raw_artist, album_artist)

            # Artist Records
            primary_artist = await self._get_or_create_artist(meta.artist)
            album_artist_obj = await self._get_or_create_artist(
                meta.album_artist
            )

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
            await self._link_multi_artists(work, primary_artist, meta.raw_artist, album_artist)

            recording = await self._get_or_create_recording(
                work.id, meta.title, meta.version_type, meta.duration, meta.isrc
            )

            # 4. Calculate file hash (MD5 for deduplication)
            file_hash = await loop.run_in_executor(
                self.executor, self._calculate_file_hash, file_path
            )

            # 5. Create LibraryFile
            await self._create_library_file(recording, file_path, file_hash, bitrate)

            # Add to VectorDB (Using Recording ID)
            self.matcher._vector_db.add_track(
                recording.id, meta.artist, meta.title
            )

            stats.created += 1

        except ID3NoHeaderError:
            stats.errors += 1
        except Exception as e:
            # logger.debug(f"Error reading {file_path}: {e}")
            raise e

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
