import shutil
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest
from airwave.core.config import settings
from airwave.core.models import (
    Artist,
    BroadcastLog,
    Recording,
    SystemSetting,
    Work,
)
from airwave.core.vector_db import VectorDB
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_match_samples_endpoint(async_client: AsyncClient, db_session):
    # 1. Setup Temp VDB and Data
    temp_dir = tempfile.mkdtemp()
    try:
        # Populate real VDB at temp path
        vdb = VectorDB(persist_path=temp_dir)

        # Create an Unmatched Log
        log = BroadcastLog(
            station_id=1,
            played_at=datetime.fromisoformat("2023-01-01T12:00:00"),
            raw_artist="Test Artist Tuner",
            raw_title="Test Title Tuner",
        )
        db_session.add(log)

        # Create a Recording (Work/Artist) that is a near match
        a = Artist(name="Test Artist Tuner")
        db_session.add(a)
        await db_session.flush()
        w = Work(title="Test Title Tuner (Live)", artist_id=a.id)
        db_session.add(w)
        await db_session.flush()
        track = Recording(
            work_id=w.id, title="Test Title Tuner (Live)", version_type="Live"
        )
        db_session.add(track)
        await db_session.commit()
        await db_session.refresh(track)  # Validation

        # Add to VDB
        vdb.add_track(track.id, "Test Artist Tuner", "Test Title Tuner (Live)")

        # Patch VectorDB to return our temp instance (or init with our path)
        with patch("airwave.core.vector_db.VectorDB", return_value=vdb):
            # 2. Call Endpoint
            resp = await async_client.get("/api/v1/admin/match-samples?limit=5")
            assert resp.status_code == 200
            data = resp.json()

            # 3. Verify
            assert len(data) > 0
            artists = [d["raw_artist"] for d in data]
            assert "Test Artist Tuner" in artists

            sample = next(
                d for d in data if d["raw_artist"] == "Test Artist Tuner"
            )
            assert len(sample["candidates"]) > 0

            candidate = sample["candidates"][0]
            assert candidate["recording_id"] == track.id
            # Score might vary but should exist
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_settings_update(async_client: AsyncClient, db_session):
    # 1. Update Settings
    payload = {
        "artist_auto": 0.99,
        "artist_review": 0.88,
        "title_auto": 0.77,
        "title_review": 0.66,
    }
    resp = await async_client.post(
        "/api/v1/admin/settings/thresholds", json=payload
    )
    assert resp.status_code == 200

    # 2. Verify Config Object Updated (Memory)
    assert settings.MATCH_VARIANT_ARTIST_SCORE == 0.99

    # 3. Verify DB Updated
    from sqlalchemy import select

    stmt = select(SystemSetting).where(
        SystemSetting.key == "MATCH_VARIANT_ARTIST_SCORE"
    )
    res = await db_session.execute(stmt)
    setting = res.scalar_one()
    assert float(setting.value) == 0.99
