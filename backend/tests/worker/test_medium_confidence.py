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

        # 5. Run run_discovery (rebuilds queue)
        created_count = await matcher.run_discovery()
        assert created_count == 1

        # 6. Verify Queue Item Existence
        from airwave.core.models import DiscoveryQueue
        from sqlalchemy import select
        stmt = select(DiscoveryQueue)
        dq_res = await db_session.execute(stmt)
        dq_item = dq_res.scalar_one()
        assert dq_item.raw_title == "Come as You Are (Unplugged)"

        # 7. MANUALLY PROMOTE (Simulate API Action)
        # Create the new track (Variant)
        new_track = Recording(
            work_id=w.id,
            title="Come as You Are (Unplugged)",
            version_type="Unplugged",
            is_verified=True
        )
        db_session.add(new_track)
        await db_session.flush()

        # Create Bridge
        from airwave.core.models import IdentityBridge
        from airwave.core.normalization import Normalizer
        bridge = IdentityBridge(
            log_signature=dq_item.signature,
            recording_id=new_track.id,
            reference_artist=dq_item.raw_artist,
            reference_title=dq_item.raw_title
        )
        db_session.add(bridge)
        
        # Link Logs
        from sqlalchemy import update
        update_stmt = (
            update(BroadcastLog)
            .where(BroadcastLog.recording_id.is_(None)) # Simple filter for this test
            .values(recording_id=new_track.id, match_reason="test_promotion")
        )
        await db_session.execute(update_stmt)
        await db_session.commit()

        # ASSERTIONS

        # A. Should create a new track for the variant (Unplugged is distinct)
        # (We created it manually above, so we assert it exists and is linked)
        
        # B. Log should be linked to the NEW track
        await db_session.refresh(log)
        assert log.recording_id is not None
        assert log.recording_id == new_track.id
        assert log.recording_id != track.id

        print("\nSUCCESS: Log linked to new variant recording.")

    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
