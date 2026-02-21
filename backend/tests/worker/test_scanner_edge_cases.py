"""Scanner edge cases: error handling, cancellation, race condition recovery."""
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("aiosqlite")

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from airwave.core.models import Album, Artist, Base, Work
from airwave.core.stats import ScanStats
from airwave.core.task_store import TaskStore
from airwave.worker.scanner import FileScanner


# --- Cancellation fixtures ---
@pytest.fixture
async def async_session():
    """Create an async SQLite session for cancellation tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def task_store():
    """Isolated TaskStore for cancellation tests."""
    return TaskStore()


# --- Error handling tests ---
class TestDatabaseErrorHandling:
    """Database error handling and recovery."""

    @pytest.mark.asyncio
    async def test_album_creation_race_condition(self, db_session):
        artist = Artist(name="test artist")
        db_session.add(artist)
        await db_session.flush()
        scanner = FileScanner(db_session)
        album1 = await scanner._get_or_create_album("test album", artist.id)
        assert album1.title == "test album"
        await db_session.commit()
        album2 = await scanner._get_or_create_album("test album", artist.id)
        assert album2.id == album1.id

    @pytest.mark.asyncio
    async def test_recording_creation_race_condition(self, db_session):
        from airwave.core.models import Recording

        artist = Artist(name="test artist")
        db_session.add(artist)
        await db_session.flush()
        work = Work(title="test work", artist_id=artist.id)
        db_session.add(work)
        await db_session.flush()
        scanner = FileScanner(db_session)
        rec1 = await scanner._upsert_recording(
            work.id, "test recording", "Original", duration=180.0
        )
        await db_session.commit()
        rec2 = await scanner._upsert_recording(
            work.id, "test recording", "Original", duration=180.0
        )
        assert rec2.id != rec1.id

    @pytest.mark.asyncio
    async def test_album_creation_with_flush_error(self, db_session):
        artist = Artist(name="test artist")
        db_session.add(artist)
        await db_session.flush()
        scanner = FileScanner(db_session)
        album = Album(title="existing album", artist_id=artist.id)
        db_session.add(album)
        await db_session.flush()
        await db_session.commit()
        original_flush = db_session.flush
        count = 0

        async def mock_flush():
            nonlocal count
            count += 1
            if count == 1:
                raise IntegrityError("UNIQUE", None, Exception("UNIQUE"))
            return await original_flush()

        with patch.object(db_session, "flush", side_effect=mock_flush):
            result = await scanner._get_or_create_album("existing album", artist.id)
        assert result.id == album.id

    @pytest.mark.asyncio
    async def test_process_file_error_recovery(self, db_session, tmp_path):
        scanner = FileScanner(db_session)
        (tmp_path / "test.flac").write_bytes(b"fake")
        with patch.object(scanner, "_extract_metadata", side_effect=Exception("Test")):
            stats = ScanStats()
            await scanner.process_file(tmp_path / "test.flac", stats)
        assert stats.errors == 1
        assert stats.created == 0

    @pytest.mark.asyncio
    async def test_multiple_errors_dont_crash_scan(self, db_session, tmp_path):
        scanner = FileScanner(db_session)
        for i in range(5):
            (tmp_path / f"test{i}.flac").write_bytes(b"fake")
        with patch.object(scanner, "_extract_metadata", side_effect=Exception("Test")):
            stats = ScanStats()
            for i in range(5):
                await scanner.process_file(tmp_path / f"test{i}.flac", stats)
        assert stats.errors == 5

    @pytest.mark.asyncio
    async def test_session_rollback_on_error(self, db_session, tmp_path):
        scanner = FileScanner(db_session)
        (tmp_path / "test.flac").write_bytes(b"fake")

        async def mock_album(*a, **k):
            raise IntegrityError("UNIQUE", None, Exception("Test"))

        with patch.object(scanner, "_get_or_create_album", side_effect=mock_album):
            with patch.object(scanner, "_extract_metadata", return_value=MagicMock()):
                stats = ScanStats()
                await scanner.process_file(tmp_path / "test.flac", stats)
        assert stats.errors == 1
        await db_session.execute(select(Artist))


# --- Cancellation tests ---
class TestCancellation:
    """Task cancellation behavior."""

    @pytest.mark.asyncio
    async def test_task_cancellation_flag(self, task_store):
        task_store.create_task("test", "scan", total=100)
        assert task_store.is_cancelled("test") is False
        assert task_store.cancel_task("test") is True
        assert task_store.is_cancelled("test") is True
        t = task_store.get_task("test")
        assert t.status == "running"
        assert t.cancel_requested is True

    @pytest.mark.asyncio
    async def test_mark_task_cancelled(self, task_store):
        task_store.create_task("test", "scan", total=100)
        task_store.cancel_task("test")
        task_store.mark_cancelled("test")
        t = task_store.get_task("test")
        assert t.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cannot_cancel_completed_task(self, task_store):
        task_store.create_task("test", "scan", total=100)
        task_store.complete_task("test", success=True)
        assert task_store.cancel_task("test") is False

    @pytest.mark.asyncio
    async def test_scanner_respects_cancellation(self, async_session, task_store):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(100):
                (Path(tmpdir) / f"song_{i}.mp3").write_bytes(b"fake")
            task_store.create_task("test", "scan", total=100)
            call_count = 0
            original_pf = FileScanner.process_file

            async def slow_pf(self, fp, stats):
                nonlocal call_count
                call_count += 1
                if call_count == 10:
                    task_store.cancel_task("test")
                await asyncio.sleep(0.01)
                return await original_pf(self, fp, stats)

            scanner = FileScanner(
                async_session, task_store=task_store, max_concurrent_files=5
            )
            with patch("airwave.worker.scanner.VectorDB"):
                with patch.object(FileScanner, "process_file", slow_pf):
                    stats = await scanner.scan_directory(tmpdir, task_id="test")
            assert task_store.get_task("test").status == "cancelled"
            assert stats.cancelled

    @pytest.mark.asyncio
    async def test_scanner_saves_progress_before_cancelling(
        self, async_session, task_store
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                (Path(tmpdir) / f"song_{i}.mp3").write_bytes(b"fake")
            task_store.create_task("test", "scan", total=50)
            call_count = 0

            async def count_pf(self, fp, stats):
                nonlocal call_count
                call_count += 1
                if call_count == 20:
                    task_store.cancel_task("test")
                return None

            scanner = FileScanner(
                async_session, task_store=task_store, max_concurrent_files=5
            )
            with patch("airwave.worker.scanner.VectorDB"):
                with patch.object(scanner, "_extract_metadata", count_pf):
                    stats = await scanner.scan_directory(tmpdir, task_id="test")
            assert stats.processed >= 20
            assert len(async_session.new) == 0
            assert len(async_session.dirty) == 0

    @pytest.mark.asyncio
    async def test_cancellation_nonexistent_task(self, task_store):
        assert task_store.cancel_task("nonexistent") is False
        assert task_store.is_cancelled("nonexistent") is False
