import pytest
from sqlalchemy import select
from airwave.core.models import DiscoveryQueue, Recording, IdentityBridge, Artist, Work
from airwave.core.normalization import Normalizer

@pytest.mark.asyncio
async def test_get_queue(async_client, db_session):
    # Setup
    item = DiscoveryQueue(
        signature="test|song",
        raw_artist="Test Artist",
        raw_title="Song Title",
        count=5
    )
    db_session.add(item)
    await db_session.commit()
    
    # Test
    resp = await async_client.get("/api/v1/discovery/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["signature"] == "test|song"
    assert data[0]["count"] == 5

@pytest.mark.asyncio
async def test_promote_item(async_client, db_session):
    # Setup
    artist = "Promo Band"
    title = "New Hit"
    sig = Normalizer.generate_signature(artist, title)
    
    item = DiscoveryQueue(
        signature=sig,
        raw_artist=artist,
        raw_title=title,
        count=1
    )
    db_session.add(item)
    await db_session.commit()
    
    # Test
    resp = await async_client.post("/api/v1/discovery/promote", json={"signature": sig})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "promoted"
    
    # Verify DB
    # 1. Queue Empty
    q = (await db_session.execute(select(DiscoveryQueue))).scalars().all()
    assert len(q) == 0
    
    # 2. Recording Created (Silver)
    rec_id = data["recording_id"]
    rec = await db_session.get(Recording, rec_id)
    assert rec is not None
    assert rec.is_verified == True
    # Normalizer might clean "New Hit" -> "new hit" or keep case depending on config. 
    # Current normalizer keeps title case usually standard or cleaned.
    
    # 3. Bridge Created
    bridge = (await db_session.execute(select(IdentityBridge))).scalar_one_or_none()
    assert bridge is not None
    assert bridge.log_signature == sig
    assert bridge.recording_id == rec.id

@pytest.mark.asyncio
async def test_link_item(async_client, db_session):
    # Setup Recording first
    artist = Artist(name="Existing Band")
    db_session.add(artist)
    await db_session.flush()
    
    work = Work(title="Existing Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    
    rec = Recording(work_id=work.id, title="Existing Song", version_type="Original", is_verified=True)
    db_session.add(rec)
    await db_session.commit() # Get ID
    
    # Setup Queue Item
    target_sig = Normalizer.generate_signature("Existing Band", "Exist Song")
    item = DiscoveryQueue(
        signature=target_sig,
        raw_artist="Existing Band",
        raw_title="Exist Song",
        count=2,
        suggested_recording_id=rec.id
    )
    db_session.add(item)
    await db_session.commit()
    
    # Test Link
    resp = await async_client.post("/api/v1/discovery/link", json={"signature": target_sig, "recording_id": rec.id})
    assert resp.status_code == 200
    
    # Verify
    q = (await db_session.execute(select(DiscoveryQueue))).scalars().all()
    assert len(q) == 0
    
    bridge = (await db_session.execute(select(IdentityBridge).where(IdentityBridge.log_signature == target_sig))).scalar_one_or_none()
    assert bridge is not None
    assert bridge.recording_id == rec.id

@pytest.mark.asyncio
async def test_dismiss_item(async_client, db_session):
    # Setup
    item = DiscoveryQueue(
        signature="skip|me",
        raw_artist="Junk",
        raw_title="Data",
        count=1
    )
    db_session.add(item)
    await db_session.commit()
    
    # Test Delete
    resp = await async_client.delete("/api/v1/discovery/skip%7Cme") # Encode pipe as %7C
    assert resp.status_code == 200
    
    # Verify Empty
    q = (await db_session.execute(select(DiscoveryQueue))).scalars().all()
    assert len(q) == 0

@pytest.mark.asyncio
async def test_relink_revivifies_bridge(async_client, db_session):
    # Setup: Create a revoked bridge
    artist_name = "Relink Artist"
    title_name = "Relink Song"
    sig = Normalizer.generate_signature(artist_name, title_name)
    
    # 1. Create Bridge (Revoked) pointing to a dummy ID (or valid one)
    # We need a valid recording to satisfy FK if strictly enforced, but let's make a real one.
    artist = Artist(name=artist_name)
    db_session.add(artist)
    await db_session.flush()
    work = Work(title=title_name, artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec1 = Recording(work_id=work.id, title=title_name, version_type="Original")
    db_session.add(rec1)
    await db_session.commit()
    
    bridge = IdentityBridge(
        log_signature=sig,
        recording_id=rec1.id,
        reference_artist=artist_name,
        reference_title=title_name,
        is_revoked=True
    )
    db_session.add(bridge)
    await db_session.commit()
    
    # 2. Setup New Recording to link to
    rec2 = Recording(work_id=work.id, title=title_name, version_type="Remaster")
    db_session.add(rec2)
    await db_session.commit()
    
    # Setup Queue Item
    item = DiscoveryQueue(
        signature=sig,
        raw_artist=artist_name,
        raw_title=title_name,
        count=1
    )
    db_session.add(item)
    await db_session.commit()
    
    # Action: Link to Rec2
    resp = await async_client.post("/api/v1/discovery/link", json={"signature": sig, "recording_id": rec2.id})
    assert resp.status_code == 200
    
    # Verify: Bridge is active and points to Rec2
    await db_session.refresh(bridge)
    assert bridge.is_revoked == False
    assert bridge.recording_id == rec2.id

@pytest.mark.asyncio
async def test_link_conflict_active_bridge(async_client, db_session):
    # Setup: Active Bridge
    artist_name = "Conflict Artist"
    title_name = "Conflict Song"
    sig = Normalizer.generate_signature(artist_name, title_name)
    
    artist = Artist(name=artist_name)
    db_session.add(artist)
    await db_session.flush()
    work = Work(title=title_name, artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec1 = Recording(work_id=work.id, title=title_name)
    db_session.add(rec1)
    
    rec2 = Recording(work_id=work.id, title=title_name, version_type="Live")
    db_session.add(rec2)
    await db_session.commit()
    
    bridge = IdentityBridge(
        log_signature=sig,
        recording_id=rec1.id,
        reference_artist=artist_name,
        reference_title=title_name,
        is_revoked=False
    )
    db_session.add(bridge)
    
    item = DiscoveryQueue(
        signature=sig, # Same sig
        raw_artist=artist_name,
        raw_title=title_name,
        count=1
    )
    db_session.add(item)
    await db_session.commit()
    
    # Action: Try to link to Rec2
    resp = await async_client.post("/api/v1/discovery/link", json={"signature": sig, "recording_id": rec2.id})
    assert resp.status_code == 409
    assert "already linked" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_signature_validation(async_client, db_session):
    # Setup Recording
    artist = Artist(name="Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Title", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="Title", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    # Setup Queue Item with INVALID signature (simulating drift/bad data)
    # The signature "valid|sig" does NOT match md5("Artist"|"Title")
    item = DiscoveryQueue(
        signature="valid|sig",
        raw_artist="Artist",
        raw_title="Title",
        count=1
    )
    db_session.add(item)
    await db_session.commit()
    
    # We request the item by its storage signature "valid|sig"
    # But the API will calculate md5("Artist", "Title") -> "somesig"
    # And check if "valid|sig" == "somesig" -> False
    
    resp = await async_client.post("/api/v1/discovery/link", json={"signature": "valid|sig", "recording_id": rec.id})
    assert resp.status_code == 400
    assert "Signature mismatch" in resp.json()["detail"]

