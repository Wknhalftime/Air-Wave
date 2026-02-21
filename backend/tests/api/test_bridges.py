
import pytest
from sqlalchemy import select
from airwave.core.models import IdentityBridge, Recording, Work, Artist
from airwave.core.normalization import Normalizer

@pytest.mark.asyncio
async def test_list_bridges(async_client, db_session):
    # Setup Data
    artist = Artist(name="Test Artist")
    db_session.add(artist)
    await db_session.flush()
    
    work = Work(title="Test Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    
    rec = Recording(work_id=work.id, title="Test Song", version_type="Original")
    db_session.add(rec)
    await db_session.commit()
    
    # Create 3 bridges
    # 1. Active, Normal
    b1 = IdentityBridge(
        log_signature="sig1",
        reference_artist="Test Artist",
        reference_title="Test Song",
        work_id=work.id,
        is_revoked=False
    )
    # 2. Revoked
    b2 = IdentityBridge(
        log_signature="sig2",
        reference_artist="Bad Artist",
        reference_title="Bad Song",
        work_id=work.id,
        is_revoked=True
    )
    # 3. Active, Different Name
    b3 = IdentityBridge(
        log_signature="sig3",
        reference_artist="Other Band",
        reference_title="Other Song",
        work_id=work.id,
        is_revoked=False
    )
    db_session.add_all([b1, b2, b3])
    await db_session.commit()
    
    # Test 1: Default List (Active Only)
    resp = await async_client.get("/api/v1/bridges/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    sigs = [d["log_signature"] for d in data]
    assert "sig1" in sigs
    assert "sig3" in sigs
    assert "sig2" not in sigs
    
    # Test 2: Include Revoked
    resp = await async_client.get("/api/v1/bridges/?include_revoked=true")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    
    # Test 3: Search
    resp = await async_client.get("/api/v1/bridges/?search=Other")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["log_signature"] == "sig3"
    
    # Test 4: Pagination
    resp = await async_client.get("/api/v1/bridges/?page_size=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

@pytest.mark.asyncio
async def test_update_bridge_status(async_client, db_session):
    # Setup
    artist = Artist(name="Status Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Status Work", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="Status Rec")
    db_session.add(rec)
    await db_session.commit()
    
    bridge = IdentityBridge(
        log_signature="status_sig",
        reference_artist="Status Artist",
        reference_title="Status Title",
        work_id=work.id,
        is_revoked=False
    )
    db_session.add(bridge)
    await db_session.commit()
    
    # Action: Revoke
    resp = await async_client.patch(f"/api/v1/bridges/{bridge.id}?is_revoked=true")
    assert resp.status_code == 200
    assert resp.json()["is_revoked"] == True
    
    # Verify DB
    await db_session.refresh(bridge)
    assert bridge.is_revoked == True
    
    # Action: Restore
    resp = await async_client.patch(f"/api/v1/bridges/{bridge.id}?is_revoked=false")
    assert resp.status_code == 200
    assert resp.json()["is_revoked"] == False
    
    # Verify DB
    await db_session.refresh(bridge)
    assert bridge.is_revoked == False

@pytest.mark.asyncio
async def test_update_nonexistent_bridge(async_client, db_session):
    resp = await async_client.patch("/api/v1/bridges/999?is_revoked=true")
    assert resp.status_code == 404
