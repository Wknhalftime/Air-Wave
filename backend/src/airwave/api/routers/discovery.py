from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy import distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import (
    Artist,
    ArtistAlias,
    BroadcastLog,
    DiscoveryQueue,
    IdentityBridge,
    Recording,
    VerificationAudit,
    Work,
)
from airwave.core.normalization import Normalizer
from airwave.worker.identity_resolver import IdentityResolver
from airwave.worker.matcher import Matcher

router = APIRouter()


class SuggestedWorkArtist(BaseModel):
    """Nested artist data for suggested work."""
    name: str

class SuggestedWork(BaseModel):
    """Nested work data for discovery queue items."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist: Optional[SuggestedWorkArtist] = None

class DiscoveryQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    signature: str
    raw_artist: str
    raw_title: str
    count: int
    suggested_work_id: Optional[int] = None  # Phase 4: Work-level suggestion
    suggested_work: Optional[SuggestedWork] = None  # Phase 4: Nested work data with artist

class LinkRequest(BaseModel):
    signature: str
    work_id: int  # Phase 4: Accept work_id instead of recording_id
    is_batch: bool = False


class PromoteRequest(BaseModel):
    signature: str
    is_batch: bool = False


def _verify_signature(queue_item, signature: str) -> None:
    """Verify signature matches queue item. Raises HTTPException on mismatch."""
    expected = Normalizer.generate_signature(
        queue_item.raw_artist, queue_item.raw_title
    )
    if signature != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Signature mismatch. Expected {expected}, got {signature}",
        )


async def _collect_logs_for_signature(db: AsyncSession, signature: str) -> list:
    """Collect BroadcastLog IDs that match the given signature (unmatched logs)."""
    stmt = select(BroadcastLog).where(BroadcastLog.work_id.is_(None))
    result = await db.execute(stmt)
    logs_to_update = []
    for log in result.scalars():
        log_sig = Normalizer.generate_signature(log.raw_artist, log.raw_title)
        if log_sig == signature:
            logs_to_update.append(log.id)
    return logs_to_update


async def _apply_identity_bridge(
    db: AsyncSession,
    signature: str,
    work_id: int,
    queue_item,
    logs_to_update: list,
    action_type: str,
    match_reason: str,
    recording_id: int | None = None,
) -> tuple:
    """Upsert bridge, update logs, create audit, delete queue item. Returns (bridge, audit)."""
    stmt = select(IdentityBridge).where(
        IdentityBridge.log_signature == signature
    )
    bridge = (await db.execute(stmt)).scalar_one_or_none()

    if bridge:
        if bridge.is_revoked:
            bridge.is_revoked = False
            bridge.work_id = work_id
            bridge.reference_artist = queue_item.raw_artist
            bridge.reference_title = queue_item.raw_title
        else:
            if bridge.work_id != work_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Conflict: This item is already linked to a "
                        "different work. Please Undo the existing link first."
                    ),
                )
    else:
        bridge = IdentityBridge(
            log_signature=signature,
            work_id=work_id,
            reference_artist=queue_item.raw_artist,
            reference_title=queue_item.raw_title,
        )
        db.add(bridge)

    await db.flush()

    if logs_to_update:
        await db.execute(
            update(BroadcastLog)
            .where(BroadcastLog.id.in_(logs_to_update))
            .values(work_id=work_id, match_reason=match_reason)
        )

    audit = VerificationAudit(
        action_type=action_type,
        signature=signature,
        raw_artist=queue_item.raw_artist,
        raw_title=queue_item.raw_title,
        recording_id=recording_id,
        log_ids=logs_to_update,
        bridge_id=bridge.id,
    )
    db.add(audit)
    await db.flush()
    await db.delete(queue_item)
    return bridge, audit


@router.get("/queue", response_model=List[DiscoveryQueueItem])
async def get_queue(
    has_suggestion: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List unmatched discovery items, sorted by count (highest impact first).
    
    Args:
        has_suggestion: Filter by suggestion status.
            - None (default): Return all items (backward compatible)
            - True: Return only items with suggestions
            - False: Return only items without suggestions
    """
    # Phase 4: Load suggested work (not recording) with eager loading
    stmt = (
        select(DiscoveryQueue)
        .options(
            selectinload(DiscoveryQueue.suggested_work)
            .selectinload(Work.artist)
        )
    )
    
    if has_suggestion is True:
        stmt = stmt.where(DiscoveryQueue.suggested_work_id.isnot(None))
    elif has_suggestion is False:
        stmt = stmt.where(DiscoveryQueue.suggested_work_id.is_(None))
    
    stmt = stmt.order_by(DiscoveryQueue.count.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/link")
async def link_discovery_item(
    req: LinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """Link a discovery signature to an existing work.

    Phase 4: Uses work_id (Identity Layer). Recording resolved at runtime.
    """
    stmt = select(DiscoveryQueue).where(DiscoveryQueue.signature == req.signature)
    queue_item = (await db.execute(stmt)).scalar_one_or_none()
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    if not await db.get(Work, req.work_id):
        raise HTTPException(status_code=404, detail="Work not found")

    _verify_signature(queue_item, req.signature)
    logs_to_update = await _collect_logs_for_signature(db, req.signature)

    action_type = "bulk_link" if req.is_batch else "link"
    bridge, audit = await _apply_identity_bridge(
        db, req.signature, req.work_id, queue_item,
        logs_to_update, action_type, "identity_bridge", recording_id=None
    )

    await db.commit()
    return {"status": "linked", "signature": req.signature, "audit_id": audit.id, "work_id": req.work_id}


@router.post("/promote")
async def promote_discovery_item(
    req: PromoteRequest,
    db: AsyncSession = Depends(get_db)
):
    """Promote a discovery item to a new Silver recording."""
    stmt = select(DiscoveryQueue).where(DiscoveryQueue.signature == req.signature)
    queue_item = (await db.execute(stmt)).scalar_one_or_none()
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    _verify_signature(queue_item, req.signature)

    clean_artist = Normalizer.clean_artist(queue_item.raw_artist)
    clean_title = Normalizer.clean(queue_item.raw_title)

    stmt_a = select(Artist).where(Artist.name == clean_artist)
    artist = (await db.execute(stmt_a)).scalar_one_or_none()
    if not artist:
        artist = Artist(name=clean_artist)
        db.add(artist)
        await db.flush()

    stmt_w = select(Work).where(
        Work.title == clean_title, Work.artist_id == artist.id
    )
    work = (await db.execute(stmt_w)).scalar_one_or_none()
    if not work:
        work = Work(title=clean_title, artist_id=artist.id)
        db.add(work)
        await db.flush()

    stmt_r = select(Recording).where(
        Recording.work_id == work.id, Recording.title == clean_title
    )
    rec = (await db.execute(stmt_r)).scalar_one_or_none()
    if not rec:
        rec = Recording(
            work_id=work.id,
            title=clean_title,
            version_type="Original",
            is_verified=True,
        )
        db.add(rec)
        await db.flush()
    elif not rec.is_verified:
        rec.is_verified = True

    logs_to_update = await _collect_logs_for_signature(db, req.signature)

    action_type = "bulk_promote" if req.is_batch else "promote"
    bridge, audit = await _apply_identity_bridge(
        db, req.signature, work.id, queue_item,
        logs_to_update, action_type, "user_verified", recording_id=rec.id
    )

    await db.commit()
    return {
        "status": "promoted",
        "recording_id": rec.id,
        "artist": clean_artist,
        "title": clean_title,
        "audit_id": audit.id,
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


class ArtistQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    raw_name: str
    item_count: int
    is_verified: bool = False
    suggested_artist: Optional[dict] = None


class ArtistLinkRequest(BaseModel):
    raw_name: str
    resolved_name: str


@router.get("/artist-queue", response_model=List[ArtistQueueItem])
async def get_artist_queue(
    limit: int = 100,
    offset: int = 0,
    filter_type: str = "all",  # "all", "matched", "unmatched"
    db: AsyncSession = Depends(get_db)
):
    """Get list of raw artist names that need linking to library artists.

    DECOUPLED FROM SONG MATCHING: Returns artists from ALL broadcast logs,
    not just unmatched songs. This allows proactive artist alias creation.

    Args:
        limit: Maximum number of artists to return
        offset: Pagination offset
        filter_type: Filter by match status:
            - "all": All artists (default)
            - "matched": Only artists from matched songs
            - "unmatched": Only artists from unmatched songs

    Returns:
        List of unique raw artist names with suggested library artist matches.
    """
    subq_verified = (
        select(ArtistAlias.raw_name)
        .where(ArtistAlias.is_verified == True)
        .scalar_subquery()
    )

    # Query BroadcastLog instead of DiscoveryQueue
    stmt = (
        select(
            BroadcastLog.raw_artist,
            func.count(BroadcastLog.id).label("item_count")
        )
        .where(
            BroadcastLog.raw_artist.notin_(subq_verified)
        )
        .group_by(BroadcastLog.raw_artist)
    )

    # Apply filter based on match status
    if filter_type == "matched":
        stmt = stmt.where(BroadcastLog.work_id.isnot(None))
    elif filter_type == "unmatched":
        stmt = stmt.where(BroadcastLog.work_id.is_(None))
    # "all" requires no additional filter

    stmt = (
        stmt
        .order_by(func.count(BroadcastLog.id).desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    rows = result.all()

    artist_queue = []
    for row in rows:
        raw_name = row.raw_artist or "Unknown Artist"
        item_count = row.item_count

        suggested = None
        clean_name = Normalizer.clean_artist(raw_name)
        library_artist = await db.execute(
            select(Artist).where(func.lower(Artist.name) == func.lower(clean_name)).limit(1)
        )
        artist_match = library_artist.scalar_one_or_none()
        if artist_match:
            suggested = {"id": artist_match.id, "name": artist_match.name}

        artist_queue.append(ArtistQueueItem(
            raw_name=raw_name,
            item_count=item_count,
            is_verified=False,
            suggested_artist=suggested
        ))

    return artist_queue


@router.post("/artist-link")
async def link_artist(
    req: ArtistLinkRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Link raw artist name to canonical library artist.
    
    Creates a verified ArtistAlias and triggers re-matching of affected items.
    """
    resolver = IdentityResolver(db)
    await resolver.add_alias(
        raw_name=req.raw_name,
        resolved_name=req.resolved_name,
        verified=True
    )
    
    affected_stmt = select(DiscoveryQueue.signature).where(
        DiscoveryQueue.raw_artist == req.raw_name
    )
    result = await db.execute(affected_stmt)
    affected_signatures = [row[0] for row in result.all()]
    
    await db.commit()
    
    if affected_signatures:
        background_tasks.add_task(
            rematch_items_for_artist,
            affected_signatures
        )
    
    return {
        "status": "success",
        "raw_name": req.raw_name,
        "resolved_name": req.resolved_name,
        "affected_items": len(affected_signatures)
    }


async def rematch_items_for_artist(signatures: List[str]):
    """Background task to re-match items after artist alias is created.

    Optimized to use batching for better performance (5-10x faster than one-at-a-time).
    """
    from airwave.api.deps import get_db_context
    from airwave.core.models import Recording

    async with get_db_context() as db:
        matcher = Matcher(db)
        updated_count = 0

        # Fetch all items at once
        stmt = select(DiscoveryQueue).where(DiscoveryQueue.signature.in_(signatures))
        result = await db.execute(stmt)
        items = result.scalars().all()

        if not items:
            logger.info("No items to rematch")
            return

        # Process in batches for efficiency (same as run_discovery)
        BATCH_SIZE = 500
        total_items = len(items)

        for i in range(0, total_items, BATCH_SIZE):
            batch_items = items[i : i + BATCH_SIZE]
            batch_queries = [(item.raw_artist, item.raw_title) for item in batch_items]

            # Batch match all items at once
            matches = await matcher.match_batch(batch_queries)

            # Process results
            for item in batch_items:
                query_key = (item.raw_artist, item.raw_title)
                match_result = matches.get(query_key)

                if match_result:
                    rec_id, reason = match_result

                    if rec_id:
                        # Phase 4: Convert recording_id to work_id
                        # Identity Bridge matches return work_id directly
                        if "Identity Bridge" in reason:
                            work_id = rec_id  # Already a work_id
                        else:
                            # Recording match - need to get work_id
                            recording = await db.get(Recording, rec_id)
                            work_id = recording.work_id if recording else None

                        if work_id and work_id != item.suggested_work_id:
                            item.suggested_work_id = work_id
                            updated_count += 1

        await db.commit()
        logger.info(f"Re-matched {updated_count} of {len(items)} items after artist link (processed in {(total_items + BATCH_SIZE - 1) // BATCH_SIZE} batches)")
