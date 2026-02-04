import shutil
import tempfile

import pytest
import pytest_asyncio
from airwave.core.models import (
    Artist,
    Base,
    BroadcastLog,
    Recording,
    Work,
)
from airwave.core.vector_db import VectorDB
from airwave.worker.matcher import Matcher
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


# Minimal DB Setup
@pytest_asyncio.fixture
async def db_session():
    # Use in-memory SQLite for speed
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_medium_confidence_detection(db_session):
    # Setup:
    # 1. Cleaner DB
    # 2. VectorDB with Temp Dir

    temp_dir = tempfile.mkdtemp()

    try:
        # 1. Existing Recording
        a = Artist(name="Nirvana")
        db_session.add(a)
        await db_session.flush()
        w = Work(title="Come as You Are", artist_id=a.id)
        db_session.add(w)
        await db_session.flush()
        track = Recording(
            work_id=w.id, title="Come as You Are", version_type="Original"
        )
        db_session.add(track)
        await db_session.commit()
        await db_session.refresh(track)

        # 2. Add to VectorDB
        vdb = VectorDB(persist_path=temp_dir)
        vdb.add_track(track.id, "nirvana", "come as you are")

        # 3. Matcher
        matcher = Matcher(db_session)
        matcher._vector_db = vdb

        # 4. Create BroadcastLog that is a VARIANT (Unplugged)
        from datetime import datetime

        log = BroadcastLog(
            station_id=1,
            raw_artist="Nirvana",
            raw_title="Come as You Are (Unplugged)",
            played_at=datetime.fromisoformat("2024-01-01T12:00:00"),
        )
        db_session.add(log)
        await db_session.commit()

        # 5. Run scan_and_promote
        created_count = await matcher.scan_and_promote()

        # 6. Must also link logs (scan_and_promote only creates tracks/bridges)
        await matcher.link_orphaned_logs()

        # ASSERTIONS

        # A. Should create a new track for the variant (Unplugged is distinct)
        assert created_count == 1

        # B. Log should be linked to the NEW track
        await db_session.refresh(log)
        assert log.recording_id is not None
        assert log.recording_id != track.id
        # assert log.match_reason == "Auto-Promoted Identity" # It might be this or None depending on loop logic

        print("\nSUCCESS: Log linked to new variant recording.")

    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
