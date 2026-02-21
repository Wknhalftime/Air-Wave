from datetime import datetime

import pytest
from sqlalchemy import select

from airwave.core.models import (
    Artist,
    ArtistAlias,
    BroadcastLog,
    DiscoveryQueue,
    IdentityBridge,
    Recording,
    Station,
    Work,
)
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
    
    # 3. Bridge Created (pointing to Work)
    bridge = (await db_session.execute(select(IdentityBridge))).scalar_one_or_none()
    assert bridge is not None
    assert bridge.log_signature == sig
    assert bridge.work_id == rec.work_id

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
        suggested_work_id=work.id
    )
    db_session.add(item)
    await db_session.commit()
    
    # Test Link (Phase 4: API accepts work_id)
    resp = await async_client.post("/api/v1/discovery/link", json={"signature": target_sig, "work_id": rec.work_id})
    assert resp.status_code == 200
    
    # Verify
    q = (await db_session.execute(select(DiscoveryQueue))).scalars().all()
    assert len(q) == 0
    
    bridge = (await db_session.execute(select(IdentityBridge).where(IdentityBridge.log_signature == target_sig))).scalar_one_or_none()
    assert bridge is not None
    assert bridge.work_id == rec.work_id

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
        work_id=work.id,
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
    
    # Action: Link to Rec2 (bridge points to work, not specific recording)
    resp = await async_client.post("/api/v1/discovery/link", json={"signature": sig, "work_id": rec2.work_id})
    assert resp.status_code == 200
    
    # Verify: Bridge is active and points to the Work
    await db_session.refresh(bridge)
    assert bridge.is_revoked == False
    assert bridge.work_id == work.id

@pytest.mark.asyncio
async def test_link_conflict_active_bridge(async_client, db_session):
    """Phase 4: Conflict occurs when linking to a recording from a DIFFERENT work.
    
    In Phase 4, bridges link to works. Linking to different recordings of the
    same work is idempotent (200 OK). But linking to a recording from a different
    work when an active bridge already exists should return 409 conflict.
    """
    # Setup: Active Bridge pointing to Work1
    artist_name = "Conflict Artist"
    title_name = "Conflict Song"
    sig = Normalizer.generate_signature(artist_name, title_name)
    
    artist = Artist(name=artist_name)
    db_session.add(artist)
    await db_session.flush()
    
    # Work 1 with bridge
    work1 = Work(title=title_name, artist_id=artist.id)
    db_session.add(work1)
    await db_session.flush()
    rec1 = Recording(work_id=work1.id, title=title_name)
    db_session.add(rec1)
    
    # Work 2 (different work) with a different recording
    work2 = Work(title="Different Song", artist_id=artist.id)
    db_session.add(work2)
    await db_session.flush()
    rec2 = Recording(work_id=work2.id, title="Different Song")
    db_session.add(rec2)
    await db_session.commit()
    
    # Bridge links to work1
    bridge = IdentityBridge(
        log_signature=sig,
        work_id=work1.id,
        reference_artist=artist_name,
        reference_title=title_name,
        is_revoked=False
    )
    db_session.add(bridge)
    
    item = DiscoveryQueue(
        signature=sig,
        raw_artist=artist_name,
        raw_title=title_name,
        count=1
    )
    db_session.add(item)
    await db_session.commit()
    
    # Action: Try to link to rec2 from work2 (DIFFERENT work) -> should conflict
    resp = await async_client.post("/api/v1/discovery/link", json={"signature": sig, "work_id": rec2.work_id})
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
    
    resp = await async_client.post("/api/v1/discovery/link", json={"signature": "valid|sig", "work_id": rec.work_id})
    assert resp.status_code == 400
    assert "Signature mismatch" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_link_queue_item_not_found(async_client, db_session):
    """Link with non-existent signature returns 404."""
    artist = Artist(name="A")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="W", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="W", version_type="Original")
    db_session.add(rec)
    await db_session.commit()
    resp = await async_client.post(
        "/api/v1/discovery/link",
        json={"signature": "nonexistent|sig", "work_id": rec.work_id},
    )
    assert resp.status_code == 404
    assert "Queue item not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_link_recording_not_found(async_client, db_session):
    """Link with valid queue item but invalid work_id returns 404."""
    sig = Normalizer.generate_signature("Band", "Song")
    item = DiscoveryQueue(signature=sig, raw_artist="Band", raw_title="Song", count=1)
    db_session.add(item)
    await db_session.commit()
    resp = await async_client.post(
        "/api/v1/discovery/link",
        json={"signature": sig, "work_id": 99999},
    )
    assert resp.status_code == 404
    assert "Work not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_dismiss_not_found(async_client):
    """Dismiss with non-existent signature returns 404."""
    resp = await async_client.delete("/api/v1/discovery/nonexistent%7Csig")
    assert resp.status_code == 404
    assert "Queue item not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_queue_limit_offset(async_client, db_session):
    """Queue supports limit and offset."""
    for i in range(5):
        item = DiscoveryQueue(
            signature=f"sig{i}|song",
            raw_artist=f"Artist{i}",
            raw_title="Song",
            count=1,
        )
        db_session.add(item)
    await db_session.commit()
    resp = await async_client.get("/api/v1/discovery/queue", params={"limit": 2, "offset": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_link_updates_unmatched_logs(async_client, db_session):
    """Link updates BroadcastLogs that match the signature (logs_to_update path)."""
    # Station for logs
    station = Station(callsign="LINK_ST")
    db_session.add(station)
    await db_session.flush()

    # Recording to link to
    artist = Artist(name="Link Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Link Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="Link Song", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    sig = Normalizer.generate_signature("Link Artist", "Link Song")
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Link Artist",
        raw_title="Link Song",
        count=2,
    )
    db_session.add(item)
    await db_session.flush()

    # Unmatched logs with same signature
    log1 = BroadcastLog(
        station_id=station.id,
        raw_artist="Link Artist",
        raw_title="Link Song",
        played_at=datetime.fromisoformat("2024-01-01T10:00:00"),
        work_id=None,
    )
    log2 = BroadcastLog(
        station_id=station.id,
        raw_artist="Link Artist",
        raw_title="Link Song",
        played_at=datetime.fromisoformat("2024-01-01T11:00:00"),
        work_id=None,
    )
    db_session.add_all([log1, log2])
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/link",
        json={"signature": sig, "work_id": rec.work_id},
    )
    assert resp.status_code == 200

    await db_session.refresh(log1)
    await db_session.refresh(log2)
    assert log1.work_id == rec.work_id
    assert log2.work_id == rec.work_id
    assert "identity_bridge" in (log1.match_reason or "")


# --- Link: idempotent and batch ---


@pytest.mark.asyncio
async def test_link_idempotent_same_recording(async_client, db_session):
    """Link with same recording as existing active bridge is idempotent (200)."""
    artist = Artist(name="Idem Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Idem Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="Idem Song", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    sig = Normalizer.generate_signature("Idem Artist", "Idem Song")
    bridge = IdentityBridge(
        log_signature=sig,
        work_id=work.id,
        reference_artist="Idem Artist",
        reference_title="Idem Song",
        is_revoked=False,
    )
    db_session.add(bridge)
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Idem Artist",
        raw_title="Idem Song",
        count=1,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/link",
        json={"signature": sig, "work_id": rec.work_id},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "linked"
    # Queue item removed, bridge still points to same rec
    q = (await db_session.execute(select(DiscoveryQueue))).scalars().all()
    assert len(q) == 0


@pytest.mark.asyncio
async def test_link_with_is_batch(async_client, db_session):
    """Link with is_batch=True creates audit with action_type bulk_link."""
    artist = Artist(name="Batch Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Batch Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="Batch Song", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    sig = Normalizer.generate_signature("Batch Artist", "Batch Song")
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Batch Artist",
        raw_title="Batch Song",
        count=1,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/link",
        json={"signature": sig, "work_id": rec.work_id, "is_batch": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "linked"
    assert "audit_id" in data
    # Verify audit has bulk_link (would need VerificationAudit query; at least no error)
    from airwave.core.models import VerificationAudit
    audit = (await db_session.execute(
        select(VerificationAudit).where(VerificationAudit.id == data["audit_id"])
    )).scalar_one_or_none()
    assert audit is not None
    assert audit.action_type == "bulk_link"


# --- Promote: not found, reuse artist/work/recording, conflict, revivify, logs, batch ---


@pytest.mark.asyncio
async def test_promote_not_found(async_client):
    """Promote with non-existent signature returns 404."""
    resp = await async_client.post(
        "/api/v1/discovery/promote",
        json={"signature": "nonexistent|sig"},
    )
    assert resp.status_code == 404
    assert "Queue item not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_promote_reuses_existing_artist_and_work(async_client, db_session):
    """Promote when artist and work already exist reuses them."""
    artist = Artist(name="reuse artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="reuse title", artist_id=artist.id)
    db_session.add(work)
    await db_session.commit()

    sig = Normalizer.generate_signature("Reuse Artist", "Reuse Title")
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Reuse Artist",
        raw_title="Reuse Title",
        count=1,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/promote",
        json={"signature": sig},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "promoted"
    # Normalizer may clean to lowercase
    assert data["recording_id"]
    # Only one artist/work (reused)
    from sqlalchemy import func
    from airwave.core.models import Artist as A, Work as W
    artist_count = (await db_session.execute(select(func.count(A.id)))).scalar_one()
    work_count = (await db_session.execute(select(func.count(W.id)))).scalar_one()
    assert artist_count == 1
    assert work_count == 1


@pytest.mark.asyncio
async def test_promote_existing_recording_sets_verified(async_client, db_session):
    """Promote when recording already exists sets is_verified=True."""
    # Use normalizer output so promote finds this artist/work/rec
    clean_artist = Normalizer.clean_artist("Verify Artist")
    clean_title = Normalizer.clean("Verify Song")
    artist = Artist(name=clean_artist)
    db_session.add(artist)
    await db_session.flush()
    work = Work(title=clean_title, artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(
        work_id=work.id,
        title=clean_title,
        version_type="Original",
        is_verified=False,
    )
    db_session.add(rec)
    await db_session.commit()

    sig = Normalizer.generate_signature("Verify Artist", "Verify Song")
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Verify Artist",
        raw_title="Verify Song",
        count=1,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/promote",
        json={"signature": sig},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recording_id"] == rec.id
    await db_session.refresh(rec)
    assert rec.is_verified is True


@pytest.mark.asyncio
async def test_promote_conflict_active_bridge(async_client, db_session):
    """Promote when active bridge points to different recording returns 409."""
    artist = Artist(name="Promo Conflict Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Promo Conflict Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec1 = Recording(work_id=work.id, title="Promo Conflict Song", version_type="Original")
    rec2 = Recording(work_id=work.id, title="Promo Conflict Song", version_type="Live")
    db_session.add_all([rec1, rec2])
    await db_session.commit()

    sig = Normalizer.generate_signature("Promo Conflict Artist", "Promo Conflict Song")
    bridge = IdentityBridge(
        log_signature=sig,
        work_id=work.id,
        reference_artist="Promo Conflict Artist",
        reference_title="Promo Conflict Song",
        is_revoked=False,
    )
    db_session.add(bridge)
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Promo Conflict Artist",
        raw_title="Promo Conflict Song",
        count=1,
    )
    db_session.add(item)
    await db_session.commit()

    # Promote would create/find rec (rec1 or rec2); bridge points to rec1
    # Code path: finds existing work/rec, then checks bridge.recording_id != rec.id
    # If promote reuses rec1, then bridge.recording_id == rec1.id -> no conflict
    # So we need bridge to point to rec1 and promote to create rec2 (new recording).
    # Actually: promote creates artist/work/rec. If artist+work exist, it finds rec.
    # So we have rec1 and rec2. Promote will find work, then find rec (first match by title).
    # So it might get rec1. Then bridge.recording_id (rec1) == rec.id (rec1) -> no conflict.
    # To get 409 we need: bridge points to rec1, promote creates or picks rec2.
    # So we need only one recording when we set up the bridge (rec1), then add rec2 after?
    # Or: have bridge -> rec1, and make sure promote creates a NEW recording (different title).
    # Easiest: artist "A", work "W", rec1. Bridge -> rec1. Queue item "A" / "W".
    # Promote: clean_artist, clean_title -> same. Finds artist, work. Finds rec1. rec = rec1.
    # bridge.recording_id = rec1, rec = rec1 -> idempotent, no 409.
    # So we need promote to create rec2. That happens when no recording exists for (work, title).
    # So: artist, work, rec1 (title "Song"). Bridge -> rec1. Queue raw "Other Artist", "Other Title"
    # so that clean gives different artist/work? Then promote creates new artist, work, rec2.
    # But then signature must match queue item. So queue item is "Other Artist", "Other Title",
    # sig = normalizer.generate("Other Artist", "Other Title"). Bridge has same sig but
    # recording_id=rec1. So we have bridge (sig, rec1), queue (sig, Other Artist, Other Title).
    # Promote: create artist "Other Artist", work "Other Title", rec2. Then bridge exists,
    # bridge.recording_id = rec1 != rec2 -> 409. So we need bridge.log_signature = sig where
    # sig = generate("Other Artist", "Other Title"). So bridge points to rec1 (some old recording),
    # queue item is Other Artist / Other Title. Promote creates rec2 for Other Artist/Other Title.
    # Then bridge.recording_id (rec1) != rec.id (rec2) -> 409. Good.
    artist2 = Artist(name="Other Artist")
    db_session.add(artist2)
    await db_session.flush()
    work2 = Work(title="Other Title", artist_id=artist2.id)
    db_session.add(work2)
    await db_session.flush()
    rec_old = Recording(work_id=work2.id, title="Other Title", version_type="Original")
    db_session.add(rec_old)
    await db_session.commit()

    sig = Normalizer.generate_signature("Other Artist", "Other Title")
    bridge = IdentityBridge(
        log_signature=sig,
        work_id=work2.id,
        reference_artist="Other Artist",
        reference_title="Other Title",
        is_revoked=False,
    )
    db_session.add(bridge)
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Other Artist",
        raw_title="Other Title",
        count=1,
    )
    db_session.add(item)
    await db_session.commit()

    # Promote will create new Artist/Work/Recording (same names, so it finds existing artist/work)
    # and then find or create Recording. If it finds rec_old, rec = rec_old, bridge.recording_id
    # == rec_old.id -> no conflict. So we need two different recordings for same work:
    # rec_old and rec_new. Promote creates "Original" if not exists. So we have rec_old
    # (Original). Promote does select Recording where work_id, title -> finds rec_old.
    # So rec = rec_old. bridge.recording_id = rec_old. So no conflict.
    # To get conflict: bridge points to rec_old. We need promote to create/find a DIFFERENT rec.
    # So we need two recordings: rec_old (Original), rec_new (Remaster). Bridge -> rec_old.
    # Promote: get artist, work (existing). Find Recording by work_id, title -> might get first.
    # So we have rec_old. So we'd get rec = rec_old. So the only way is: bridge points to rec1,
    # and promote creates a brand new recording (so we need no recording to exist for that work+title).
    # So: Queue "New Artist" / "New Song". No artist, no work, no recording. Bridge with
    # sig = generate("New Artist", "New Song") and recording_id = rec_old (some other rec).
    # So we need a recording that exists - any rec. So rec_old is for something else. Bridge
    # has log_signature = sig("New Artist", "New Song") and recording_id = rec_old.id.
    # Promote: create artist "New Artist", work "New Song", rec_new. bridge.recording_id = rec_old,
    # rec = rec_new -> 409. Yes.
    artist_other = Artist(name="Unrelated")
    db_session.add(artist_other)
    await db_session.flush()
    work_other = Work(title="Unrelated", artist_id=artist_other.id)
    db_session.add(work_other)
    await db_session.flush()
    rec_unrelated = Recording(
        work_id=work_other.id,
        title="Unrelated",
        version_type="Original",
    )
    db_session.add(rec_unrelated)
    await db_session.commit()

    sig = Normalizer.generate_signature("New Artist", "New Song")
    bridge = IdentityBridge(
        log_signature=sig,
        work_id=work_other.id,
        reference_artist="New Artist",
        reference_title="New Song",
        is_revoked=False,
    )
    db_session.add(bridge)
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="New Artist",
        raw_title="New Song",
        count=1,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/promote",
        json={"signature": sig},
    )
    assert resp.status_code == 409
    assert "already linked" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_promote_revivifies_bridge(async_client, db_session):
    """Promote when revoked bridge exists revivifies it and uses new recording."""
    artist = Artist(name="Promo Rev Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Promo Rev Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec_old = Recording(work_id=work.id, title="Promo Rev Song", version_type="Original")
    db_session.add(rec_old)
    await db_session.commit()

    sig = Normalizer.generate_signature("Promo Rev Artist", "Promo Rev Song")
    bridge = IdentityBridge(
        log_signature=sig,
        work_id=work.id,
        reference_artist="Promo Rev Artist",
        reference_title="Promo Rev Song",
        is_revoked=True,
    )
    db_session.add(bridge)
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Promo Rev Artist",
        raw_title="Promo Rev Song",
        count=1,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/promote",
        json={"signature": sig},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "promoted"
    # Promote creates/finds a recording; bridge should point to its work and be active
    await db_session.refresh(bridge)
    assert bridge.is_revoked is False
    # Bridge points to work, verify recording's work matches
    rec_result = await db_session.get(Recording, data["recording_id"])
    assert bridge.work_id == rec_result.work_id


@pytest.mark.asyncio
async def test_promote_updates_unmatched_logs(async_client, db_session):
    """Promote with unmatched logs matching signature updates them (user_verified)."""
    station = Station(callsign="PROMO_ST")
    db_session.add(station)
    await db_session.flush()

    sig = Normalizer.generate_signature("Promo Log Artist", "Promo Log Song")
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Promo Log Artist",
        raw_title="Promo Log Song",
        count=2,
    )
    db_session.add(item)
    await db_session.flush()

    log1 = BroadcastLog(
        station_id=station.id,
        raw_artist="Promo Log Artist",
        raw_title="Promo Log Song",
        played_at=datetime.fromisoformat("2024-01-01T10:00:00"),
        work_id=None,
    )
    log2 = BroadcastLog(
        station_id=station.id,
        raw_artist="Promo Log Artist",
        raw_title="Promo Log Song",
        played_at=datetime.fromisoformat("2024-01-01T11:00:00"),
        work_id=None,
    )
    db_session.add_all([log1, log2])
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/promote",
        json={"signature": sig},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "promoted"
    rec_id = data["recording_id"]

    # Get the recording's work_id
    rec_result = await db_session.get(Recording, rec_id)
    await db_session.refresh(log1)
    await db_session.refresh(log2)
    assert log1.work_id == rec_result.work_id
    assert log2.work_id == rec_result.work_id
    assert "user_verified" in (log1.match_reason or "")


@pytest.mark.asyncio
async def test_promote_with_is_batch(async_client, db_session):
    """Promote with is_batch=True creates audit with action_type bulk_promote."""
    sig = Normalizer.generate_signature("Bulk Promo Artist", "Bulk Promo Song")
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Bulk Promo Artist",
        raw_title="Bulk Promo Song",
        count=1,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/promote",
        json={"signature": sig, "is_batch": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "promoted"
    from airwave.core.models import VerificationAudit
    audit = (await db_session.execute(
        select(VerificationAudit).order_by(VerificationAudit.id.desc()).limit(1)
    )).scalars().first()
    assert audit is not None
    assert audit.action_type == "bulk_promote"


# --- Queue: suggested_recording load ---


@pytest.mark.asyncio
async def test_get_queue_includes_suggested_recording(async_client, db_session):
    """Queue item with suggested_recording_id loads suggested recording (selectinload)."""
    artist = Artist(name="Suggest Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Suggest Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="Suggest Song", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    sig = Normalizer.generate_signature("Suggest Artist", "Suggest Song")
    item = DiscoveryQueue(
        signature=sig,
        raw_artist="Suggest Artist",
        raw_title="Suggest Song",
        count=3,
        suggested_work_id=work.id,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.get("/api/v1/discovery/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["signature"] == sig
    assert data[0]["suggested_work_id"] == work.id


# =============================================================================
# Tests for has_suggestion filter (Problem 3 - Verification Hub Redesign)
# =============================================================================


@pytest.mark.asyncio
async def test_get_queue_has_suggestion_true(async_client, db_session):
    """Queue with has_suggestion=true returns only items with suggestions."""
    # Create recording for suggested item
    artist = Artist(name="Suggested Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Suggested Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="Suggested Song", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    # Create items: one with suggestion, one without
    sig_with = Normalizer.generate_signature("Suggested Artist", "Suggested Song")
    item_with = DiscoveryQueue(
        signature=sig_with,
        raw_artist="Suggested Artist",
        raw_title="Suggested Song",
        count=5,
        suggested_work_id=work.id,
    )
    item_without = DiscoveryQueue(
        signature="no|suggestion",
        raw_artist="Unknown",
        raw_title="Mystery",
        count=3,
        suggested_work_id=None,
    )
    db_session.add_all([item_with, item_without])
    await db_session.commit()

    resp = await async_client.get("/api/v1/discovery/queue", params={"has_suggestion": True})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["signature"] == sig_with
    assert data[0]["suggested_work_id"] == work.id


@pytest.mark.asyncio
async def test_get_queue_has_suggestion_false(async_client, db_session):
    """Queue with has_suggestion=false returns only items without suggestions."""
    # Create recording for suggested item
    artist = Artist(name="Has Suggest Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="Has Suggest Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="Has Suggest Song", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    sig_with = Normalizer.generate_signature("Has Suggest Artist", "Has Suggest Song")
    item_with = DiscoveryQueue(
        signature=sig_with,
        raw_artist="Has Suggest Artist",
        raw_title="Has Suggest Song",
        count=5,
        suggested_work_id=work.id,
    )
    item_without = DiscoveryQueue(
        signature="none|here",
        raw_artist="No Suggestion",
        raw_title="None Here",
        count=3,
        suggested_work_id=None,
    )
    db_session.add_all([item_with, item_without])
    await db_session.commit()

    resp = await async_client.get("/api/v1/discovery/queue", params={"has_suggestion": False})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["signature"] == "none|here"
    assert data[0]["suggested_work_id"] is None


@pytest.mark.asyncio
async def test_get_queue_has_suggestion_none_returns_all(async_client, db_session):
    """Queue without has_suggestion param (None) returns all items (backward compatible)."""
    artist = Artist(name="All Artist")
    db_session.add(artist)
    await db_session.flush()
    work = Work(title="All Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    rec = Recording(work_id=work.id, title="All Song", version_type="Original")
    db_session.add(rec)
    await db_session.commit()

    sig_with = Normalizer.generate_signature("All Artist", "All Song")
    item_with = DiscoveryQueue(
        signature=sig_with,
        raw_artist="All Artist",
        raw_title="All Song",
        count=5,
        suggested_work_id=work.id,
    )
    item_without = DiscoveryQueue(
        signature="all|none",
        raw_artist="All None",
        raw_title="No Suggest",
        count=3,
        suggested_work_id=None,
    )
    db_session.add_all([item_with, item_without])
    await db_session.commit()

    # No has_suggestion param - should return all
    resp = await async_client.get("/api/v1/discovery/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


# =============================================================================
# Tests for Artist Queue (Problem 4 - Verification Hub Redesign)
# =============================================================================


@pytest.mark.asyncio
async def test_get_artist_queue_basic(async_client, db_session):
    """Artist queue returns unique raw artist names from BroadcastLogs, sorted by item count."""
    station = Station(callsign="ARTQ_ST")
    db_session.add(station)
    await db_session.flush()

    # BroadcastLog-based: artist queue queries BroadcastLog, not DiscoveryQueue
    for _ in range(2):
        db_session.add(BroadcastLog(
            station_id=station.id, played_at=datetime.now(),
            raw_artist="Raw Artist One", raw_title="Song One",
        ))
    db_session.add(BroadcastLog(
        station_id=station.id, played_at=datetime.now(),
        raw_artist="Raw Artist Two", raw_title="Song One",
    ))
    await db_session.commit()

    resp = await async_client.get("/api/v1/discovery/artist-queue")
    assert resp.status_code == 200
    data = resp.json()
    
    # Should return 2 unique artists
    assert len(data) == 2
    
    # Sorted by item_count (number of queue items, not play count)
    # Raw Artist One has 2 items, Raw Artist Two has 1 item
    assert data[0]["raw_name"] == "Raw Artist One"
    assert data[0]["item_count"] == 2
    assert data[1]["raw_name"] == "Raw Artist Two"
    assert data[1]["item_count"] == 1


@pytest.mark.asyncio
async def test_get_artist_queue_excludes_verified_aliases(async_client, db_session):
    """Artist queue excludes artists that already have verified aliases."""
    alias = ArtistAlias(
        raw_name="Verified Raw",
        resolved_name="Canonical Name",
        is_verified=True,
    )
    db_session.add(alias)
    await db_session.flush()

    station = Station(callsign="ARTQ_ST2")
    db_session.add(station)
    await db_session.flush()

    db_session.add(BroadcastLog(
        station_id=station.id, played_at=datetime.now(),
        raw_artist="Verified Raw", raw_title="Some Song",
    ))
    db_session.add(BroadcastLog(
        station_id=station.id, played_at=datetime.now(),
        raw_artist="Unverified Raw", raw_title="Other Song",
    ))
    await db_session.commit()

    resp = await async_client.get("/api/v1/discovery/artist-queue")
    assert resp.status_code == 200
    data = resp.json()
    
    # Only unverified artist should appear
    assert len(data) == 1
    assert data[0]["raw_name"] == "Unverified Raw"


@pytest.mark.asyncio
async def test_get_artist_queue_includes_suggested_artist(async_client, db_session):
    """Artist queue includes suggested library artist when name matches."""
    library_artist = Artist(name="Test Artist")
    db_session.add(library_artist)
    await db_session.flush()

    station = Station(callsign="ARTQ_ST3")
    db_session.add(station)
    await db_session.flush()

    db_session.add(BroadcastLog(
        station_id=station.id, played_at=datetime.now(),
        raw_artist="Test Artist", raw_title="Test Song",
    ))
    await db_session.commit()

    resp = await async_client.get("/api/v1/discovery/artist-queue")
    assert resp.status_code == 200
    data = resp.json()
    
    assert len(data) == 1
    assert data[0]["raw_name"] == "Test Artist"
    assert data[0]["suggested_artist"] is not None
    assert data[0]["suggested_artist"]["id"] == library_artist.id
    assert data[0]["suggested_artist"]["name"] == "Test Artist"


@pytest.mark.asyncio
async def test_get_artist_queue_limit_offset(async_client, db_session):
    """Artist queue supports limit and offset pagination."""
    station = Station(callsign="ARTQ_ST4")
    db_session.add(station)
    await db_session.flush()

    for i in range(5):
        db_session.add(BroadcastLog(
            station_id=station.id, played_at=datetime.now(),
            raw_artist=f"Artist {i}", raw_title="Song",
        ))
    await db_session.commit()

    resp = await async_client.get(
        "/api/v1/discovery/artist-queue",
        params={"limit": 2, "offset": 1}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


# =============================================================================
# Tests for Artist Link (Problem 4 - Verification Hub Redesign)
# =============================================================================


@pytest.mark.asyncio
async def test_artist_link_creates_verified_alias(async_client, db_session):
    """Artist link creates a verified ArtistAlias entry."""
    # Create a discovery item
    item = DiscoveryQueue(
        signature="link|song",
        raw_artist="Misspelled Artsit",
        raw_title="Good Song",
        count=5,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/artist-link",
        json={
            "raw_name": "Misspelled Artsit",
            "resolved_name": "Correct Artist",
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["raw_name"] == "Misspelled Artsit"
    assert data["resolved_name"] == "Correct Artist"
    assert data["affected_items"] == 1

    # Verify alias was created
    stmt = select(ArtistAlias).where(ArtistAlias.raw_name == "Misspelled Artsit")
    result = await db_session.execute(stmt)
    alias = result.scalar_one_or_none()
    
    assert alias is not None
    assert alias.resolved_name == "Correct Artist"
    assert alias.is_verified is True


@pytest.mark.asyncio
async def test_artist_link_updates_existing_alias(async_client, db_session):
    """Artist link updates an existing alias if one exists."""
    # Create existing unverified alias
    existing_alias = ArtistAlias(
        raw_name="Old Spelling",
        resolved_name="Wrong Artist",
        is_verified=False,
    )
    db_session.add(existing_alias)
    
    # Create discovery item
    item = DiscoveryQueue(
        signature="update|song",
        raw_artist="Old Spelling",
        raw_title="A Song",
        count=3,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/artist-link",
        json={
            "raw_name": "Old Spelling",
            "resolved_name": "Right Artist",
        }
    )
    assert resp.status_code == 200

    # Verify alias was updated
    await db_session.refresh(existing_alias)
    assert existing_alias.resolved_name == "Right Artist"
    assert existing_alias.is_verified is True


@pytest.mark.asyncio
async def test_artist_link_counts_affected_items(async_client, db_session):
    """Artist link returns correct count of affected items."""
    # Create multiple items with same raw artist
    for i in range(3):
        item = DiscoveryQueue(
            signature=f"multi|song{i}",
            raw_artist="Common Artist",
            raw_title=f"Song {i}",
            count=1,
        )
        db_session.add(item)
    
    # Create item with different artist
    other_item = DiscoveryQueue(
        signature="other|song",
        raw_artist="Other Artist",
        raw_title="Different Song",
        count=1,
    )
    db_session.add(other_item)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/discovery/artist-link",
        json={
            "raw_name": "Common Artist",
            "resolved_name": "Canonical Artist",
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["affected_items"] == 3  # Only items with "Common Artist"


@pytest.mark.asyncio
async def test_artist_link_no_affected_items(async_client, db_session):
    """Artist link works even with no matching queue items."""
    # No discovery items exist for this artist
    resp = await async_client.post(
        "/api/v1/discovery/artist-link",
        json={
            "raw_name": "Nonexistent Artist",
            "resolved_name": "Some Artist",
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["affected_items"] == 0

    # Alias should still be created
    stmt = select(ArtistAlias).where(ArtistAlias.raw_name == "Nonexistent Artist")
    result = await db_session.execute(stmt)
    alias = result.scalar_one_or_none()
    assert alias is not None
