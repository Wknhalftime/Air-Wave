from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import (
    Artist,
    BroadcastLog,
    DiscoveryQueue,
    IdentityBridge,
    Recording,
    VerificationAudit,
    Work,
)
from airwave.core.normalization import Normalizer

router = APIRouter()


class DiscoveryQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    signature: str
    raw_artist: str
    raw_title: str
    count: int
    suggested_recording_id: Optional[int]

class LinkRequest(BaseModel):
    signature: str
    recording_id: int
    is_batch: bool = False

class PromoteRequest(BaseModel):
    signature: str
    is_batch: bool = False

@router.get("/queue", response_model=List[DiscoveryQueueItem])
async def get_queue(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List unmatched discovery items, sorted by count (highest impact first)."""
    stmt = (
        select(DiscoveryQueue)
        .options(
            selectinload(DiscoveryQueue.suggested_recording)
            .selectinload(Recording.work)
            .selectinload(Work.artist)
        )
        .order_by(DiscoveryQueue.count.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/link")
async def link_discovery_item(
    req: LinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """Link a discovery signature to an existing recording."""
    # 1. Verify Queue Item exists
    stmt = select(DiscoveryQueue).where(DiscoveryQueue.signature == req.signature)
    res = await db.execute(stmt)
    queue_item = res.scalar_one_or_none()

    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    # 2. Verify Recording exists
    rec = await db.get(Recording, req.recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    # 3. Collect affected BroadcastLog IDs BEFORE updating them
    unmatched_logs_stmt = select(BroadcastLog).where(
        BroadcastLog.recording_id.is_(None)
    )
    unmatched_logs = await db.execute(unmatched_logs_stmt)
    logs_to_update = []

    for log in unmatched_logs.scalars():
        log_sig = Normalizer.generate_signature(log.raw_artist, log.raw_title)
        if log_sig == req.signature:
            logs_to_update.append(log.id)

    # 3b. Verify Signature Integrity (AC 3)
    # The signature in the request MUST match the hash of the raw
    # data in the queue. This prevents UI/API drift or malicious inputs.
    expected_sig = Normalizer.generate_signature(
        queue_item.raw_artist, queue_item.raw_title
    )
    if req.signature != expected_sig:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Signature mismatch. Expected {expected_sig}, "
                f"got {req.signature}"
            )
        )

    # 4. Upsert IdentityBridge (AC 1, 2, 4)
    # Check for EXISTING bridge (Active or Revoked)
    stmt = select(IdentityBridge).where(
        IdentityBridge.log_signature == req.signature
    )
    bridge = (await db.execute(stmt)).scalar_one_or_none()

    if bridge:
        if bridge.is_revoked:
            # AC 2: Revivification (Re-Link)
            bridge.is_revoked = False
            bridge.recording_id = req.recording_id
            bridge.reference_artist = queue_item.raw_artist
            bridge.reference_title = queue_item.raw_title
            # We don't need to add() it, it's attached to session
        else:
            # AC 4: Conflict Prevention (Active Bridge Exists)
            if bridge.recording_id != req.recording_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Conflict: This item is already linked to a "
                        "different recording. Please Undo the existing "
                        "link first."
                    )
                )
            # If recording_id matches, it's a no-op (idempotent)
    else:
        # AC 1: Create New Bridge
        bridge = IdentityBridge(
            log_signature=req.signature,
            recording_id=req.recording_id,
            reference_artist=queue_item.raw_artist,
            reference_title=queue_item.raw_title
        )
        db.add(bridge)

    await db.flush()  # Ensure bridge ID is available

    # 5. Update BroadcastLogs (AC 2: Update logs even if bridge existed)
    # We always re-scan logs because the "Revivification" might imply
    # we missed some, or if we are switching from a "Ghost" state.
    if logs_to_update:
        update_stmt = (
            update(BroadcastLog)
            .where(BroadcastLog.id.in_(logs_to_update))
            .values(
                recording_id=req.recording_id,
                match_reason="identity_bridge"
            )
        )
        await db.execute(update_stmt)

    # 6. Create VerificationAudit entry
    action_type = "bulk_link" if req.is_batch else "link"
    audit = VerificationAudit(
        action_type=action_type,
        signature=req.signature,
        raw_artist=queue_item.raw_artist,
        raw_title=queue_item.raw_title,
        recording_id=req.recording_id,
        log_ids=logs_to_update,
        bridge_id=bridge.id
    )
    db.add(audit)
    await db.flush()  # Get audit ID

    # 7. Delete from Queue
    await db.delete(queue_item)

    await db.commit()
    return {"status": "linked", "signature": req.signature, "audit_id": audit.id}


@router.post("/promote")
async def promote_discovery_item(
    req: PromoteRequest,
    db: AsyncSession = Depends(get_db)
):
    """Promote a discovery item to a new Silver recording."""
    stmt = select(DiscoveryQueue).where(DiscoveryQueue.signature == req.signature)
    res = await db.execute(stmt)
    queue_item = res.scalar_one_or_none()

    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    # Create Artist/Work/Recording hierarchy logic (copied/refactored from matcher?)
    # For MVP, simple creation:

    clean_artist = Normalizer.clean_artist(queue_item.raw_artist)
    clean_title = Normalizer.clean(queue_item.raw_title)

    # 1. Get/Create Artist
    stmt_a = select(Artist).where(Artist.name == clean_artist)
    artist = (await db.execute(stmt_a)).scalar_one_or_none()
    if not artist:
        artist = Artist(name=clean_artist)
        db.add(artist)
        await db.flush()

    # 2. Get/Create Work
    stmt_w = select(Work).where(
        Work.title == clean_title, Work.artist_id == artist.id
    )
    work = (await db.execute(stmt_w)).scalar_one_or_none()
    if not work:
        work = Work(title=clean_title, artist_id=artist.id)
        db.add(work)
        await db.flush()

    # 3. Create Recording (Silver)
    # Check if exists first to avoid dupes?
    stmt_r = select(Recording).where(
        Recording.work_id == work.id, Recording.title == clean_title
    )
    rec = (await db.execute(stmt_r)).scalar_one_or_none()

    if not rec:
        rec = Recording(
            work_id=work.id,
            title=clean_title,
            version_type="Original",
            is_verified=True, # Explicit promotion = Silver
            # status="SILVER" ? We decided on is_verified=True
        )
        db.add(rec)
        await db.flush()
    else:
        # If it exists, we are essentially Linking to it + setting verified?
        if not rec.is_verified:
             rec.is_verified = True

    # 3b. Verify Signature Integrity (AC 3)
    expected_sig = Normalizer.generate_signature(
        queue_item.raw_artist, queue_item.raw_title
    )
    if req.signature != expected_sig:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Signature mismatch. Expected {expected_sig}, "
                f"got {req.signature}"
            )
        )

    # 3c. Collect affected BroadcastLog IDs
    unmatched_logs_stmt = select(BroadcastLog).where(
        BroadcastLog.recording_id.is_(None)
    )
    unmatched_logs = await db.execute(unmatched_logs_stmt)
    logs_to_update = []

    for log in unmatched_logs.scalars():
        log_sig = Normalizer.generate_signature(log.raw_artist, log.raw_title)
        if log_sig == req.signature:
            logs_to_update.append(log.id)

    # 4. Upsert IdentityBridge (AC 1, 2, 4)
    stmt = select(IdentityBridge).where(
        IdentityBridge.log_signature == req.signature
    )
    bridge = (await db.execute(stmt)).scalar_one_or_none()

    if bridge:
        if bridge.is_revoked:
            # AC 2: Revivification
            bridge.is_revoked = False
            bridge.recording_id = rec.id
            bridge.reference_artist = queue_item.raw_artist
            bridge.reference_title = queue_item.raw_title
        else:
            # AC 4: Conflict Prevention
            if bridge.recording_id != rec.id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Conflict: This item is already linked to a "
                        "different recording. Please Undo the existing "
                        "link first."
                    )
                )
    else:
        bridge = IdentityBridge(
            log_signature=req.signature,
            recording_id=rec.id,
            reference_artist=queue_item.raw_artist,
            reference_title=queue_item.raw_title
        )
        db.add(bridge)

    await db.flush()

    # 5. Update BroadcastLogs
    if logs_to_update:
        update_stmt = (
            update(BroadcastLog)
            .where(BroadcastLog.id.in_(logs_to_update))
            .values(
                recording_id=rec.id,
                match_reason="user_verified"
            )
        )
        await db.execute(update_stmt)

    # 6. Create VerificationAudit entry
    action_type = "bulk_promote" if req.is_batch else "promote"
    audit = VerificationAudit(
        action_type=action_type,
        signature=req.signature,
        raw_artist=queue_item.raw_artist,
        raw_title=queue_item.raw_title,
        recording_id=rec.id,
        log_ids=logs_to_update,
        bridge_id=bridge.id
    )
    db.add(audit)
    await db.flush()

    # 7. Delete from Queue
    await db.delete(queue_item)

    await db.commit()
    return {
        "status": "promoted",
        "recording_id": rec.id,
        "artist": clean_artist,
        "title": clean_title,
        "audit_id": audit.id
    }

@router.delete("/{signature}")
async def dismiss_discovery_item(signature: str, db: AsyncSession = Depends(get_db)):
    """Dismiss/Delete an item from the queue (Hide noise)."""
    stmt = select(DiscoveryQueue).where(DiscoveryQueue.signature == signature)
    res = await db.execute(stmt)
    queue_item = res.scalar_one_or_none()

    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    await db.delete(queue_item)
    await db.commit()
    return {"status": "dismissed"}
