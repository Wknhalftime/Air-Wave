from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import (
    Artist,
    ArtistAlias,
    BroadcastLog,
    DiscoveryQueue,
    IdentityBridge,
    ProposedSplit,
    Recording,
    Work,
    VerificationAudit,
)
from airwave.core.normalization import Normalizer
from airwave.worker.identity_resolver import IdentityResolver

router = APIRouter()


class ArtistAliasSchema(BaseModel):
    id: int
    raw_name: str
    resolved_name: str | None
    is_verified: bool
    is_null: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProposedSplitSchema(BaseModel):
    id: int
    raw_artist: str
    proposed_artists: List[str]
    status: str
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecordingSimpleSchema(BaseModel):
    id: int
    title: str
    artist: str

    model_config = ConfigDict(from_attributes=True)


class IdentityBridgeSchema(BaseModel):
    id: int
    raw_artist: str
    raw_title: str
    recording: RecordingSimpleSchema
    confidence: float
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class VerificationAuditSchema(BaseModel):
    id: int
    created_at: datetime
    action_type: str
    raw_artist: str
    raw_title: str
    recording_title: Optional[str] = None
    recording_artist: Optional[str] = None
    log_count: int
    can_undo: bool
    undone_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class CreateBridgeRequest(BaseModel):
    raw_artist: str
    raw_title: str
    recording_id: int


class CreateAliasRequest(BaseModel):
    raw_name: str
    resolved_name: str


class UpdateAliasRequest(BaseModel):
    resolved_name: str | None


class UpdateSplitRequest(BaseModel):
    proposed_artists: List[str]


@router.get("/bridges", response_model=List[IdentityBridgeSchema])
async def get_bridges(
    skip: int = 0,
    limit: int = 50,
    term: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all Identity Bridge entries with optional search.
    
    Phase 4: Returns work info (not recording). Use RecordingResolver for files.
    """
    stmt = (
        select(IdentityBridge)
        .options(
            selectinload(IdentityBridge.work)
            .selectinload(Work.artist)
        )
        .order_by(IdentityBridge.updated_at.desc())
    )

    if term:
        search = f"%{term}%"
        stmt = stmt.where(
            or_(
                IdentityBridge.reference_artist.ilike(search),
                IdentityBridge.reference_title.ilike(search),
            )
        )

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    bridges = result.scalars().all()

    # Phase 4: Map to schema using work info
    resp = []
    for b in bridges:
        artist_name = "Unknown"
        work_title = "Unknown"
        if b.work:
            work_title = b.work.title
            if b.work.artist:
                artist_name = b.work.artist.name
            
        resp.append({
            "id": b.id,
            "raw_artist": b.reference_artist,
            "raw_title": b.reference_title,
            "recording": {  # Keep schema compatibility but return work info
                "id": b.work_id,
                "title": work_title,
                "artist": artist_name
            },
            "confidence": b.confidence,
            "created_at": b.created_at
        })

    return resp


@router.delete("/bridges/{id}")
async def delete_bridge(id: int, db: AsyncSession = Depends(get_db)):
    """Delete an Identity Bridge entry.
    
    WARNING: This will cause logs using this bridge to become unmatched.
    """
    stmt = select(IdentityBridge).where(IdentityBridge.id == id)
    result = await db.execute(stmt)
    bridge = result.scalar_one_or_none()
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Bridge not found")
    
    # Phase 4: Check logs by work_id
    log_stmt = select(func.count(BroadcastLog.id)).where(
        BroadcastLog.match_reason.like("%Identity Bridge%"),
        BroadcastLog.work_id == bridge.work_id
    )
    log_count = await db.execute(log_stmt)
    count = log_count.scalar() or 0
    
    bridge.is_revoked = True
    await db.commit()
    
    return {
        "message": "Bridge revoked (soft-deleted)",
        "affected_logs": count,
        "warning": "Affected logs will need re-matching"
    }


@router.post("/bridges")
async def create_bridge(
    req: CreateBridgeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Manually create an Identity Bridge (Teach the AI).
    
    Phase 4: Creates bridge with work_id extracted from recording.
    """
    
    # Verify recording exists and get work_id
    rec_stmt = select(Recording).where(Recording.id == req.recording_id)
    rec_res = await db.execute(rec_stmt)
    recording = rec_res.scalar_one_or_none()
    
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    work_id = recording.work_id
    if not work_id:
        raise HTTPException(
            status_code=400, 
            detail="Recording does not have a work_id. Cannot create identity bridge."
        )
    
    # Generate signature
    signature = Normalizer.generate_signature(req.raw_artist, req.raw_title)
    
    # Check for existing bridge
    existing_stmt = select(IdentityBridge).where(
        IdentityBridge.log_signature == signature
    )
    existing_res = await db.execute(existing_stmt)
    existing = existing_res.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Bridge already exists for this artist/title pair"
        )
    
    # Phase 4: Create bridge with work_id only
    bridge = IdentityBridge(
        log_signature=signature,
        reference_artist=req.raw_artist,
        reference_title=req.raw_title,
        work_id=work_id,
        confidence=1.0
    )
    db.add(bridge)
    await db.flush()

    # Create VerificationAudit entry
    audit = VerificationAudit(
        action_type="manual_bridge",
        signature=signature,
        raw_artist=req.raw_artist,
        raw_title=req.raw_title,
        recording_id=req.recording_id,  # Keep for audit trail
        log_ids=[],
        bridge_id=bridge.id
    )
    db.add(audit)
    
    await db.commit()
    
    return {"message": "Bridge created", "id": bridge.id, "audit_id": audit.id, "work_id": work_id}


@router.post("/aliases")
async def create_alias(
    req: CreateAliasRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create or update an Artist Alias."""
    resolver = IdentityResolver(db)
    await resolver.add_alias(req.raw_name, req.resolved_name, verified=True)
    await db.commit()
    
    return {"message": "Alias created/updated"}


@router.delete("/aliases/{id}")
async def delete_alias(id: int, db: AsyncSession = Depends(get_db)):
    """Delete an Artist Alias."""
    stmt = select(ArtistAlias).where(ArtistAlias.id == id)
    result = await db.execute(stmt)
    alias = result.scalar_one_or_none()
    
    if not alias:
        raise HTTPException(status_code=404, detail="Alias not found")
    
    await db.delete(alias)
    await db.commit()
    
    return {"message": "Alias deleted"}


@router.put("/aliases/{alias_id}")
async def update_alias(
    alias_id: int,
    req: UpdateAliasRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update an Artist Alias resolved name."""
    stmt = select(ArtistAlias).where(ArtistAlias.id == alias_id)
    result = await db.execute(stmt)
    alias = result.scalar_one_or_none()

    if not alias:
        raise HTTPException(status_code=404, detail="Alias not found")

    alias.resolved_name = req.resolved_name
    alias.is_verified = True
    await db.commit()

    return {"message": "Alias updated", "id": alias.id}


@router.get("/splits/pending", response_model=List[ProposedSplitSchema])
async def get_pending_splits(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(ProposedSplit)
        .where(ProposedSplit.status == "PENDING")
        .order_by(ProposedSplit.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/splits/{split_id}/confirm")
async def confirm_split(split_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(ProposedSplit).where(ProposedSplit.id == split_id)
    result = await db.execute(stmt)
    split = result.scalar_one_or_none()

    if not split:
        raise HTTPException(status_code=404, detail="Split proposal not found")

    # Update status
    split.status = "APPROVED"

    # Join the proposed artists for the alias map (e.g. "Artist A; Artist B")
    # Using semicolon as it's rare in artist names and not used in splitting logic
    resolved_name = "; ".join(split.proposed_artists)

    resolver = IdentityResolver(db)
    # Confirmation means the system will treat this raw string as the joined version
    await resolver.add_alias(split.raw_artist, resolved_name, verified=True)

    await db.commit()
    return {
        "message": "Split confirmed",
        "raw_artist": split.raw_artist,
        "resolved_as": resolved_name,
    }


@router.post("/splits/{split_id}/reject")
async def reject_split(split_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(ProposedSplit).where(ProposedSplit.id == split_id)
    result = await db.execute(stmt)
    split = result.scalar_one_or_none()

    if not split:
        raise HTTPException(status_code=404, detail="Split proposal not found")

    split.status = "REJECTED"

    # Add negative alias mapping so we treat it as single entity (raw -> raw)
    # This prevents the heuristic from suggesting a split again
    resolver = IdentityResolver(db)
    await resolver.add_alias(split.raw_artist, split.raw_artist, verified=True)

    await db.commit()
    return {"message": "Split rejected, treated as single entity"}


@router.put("/splits/{split_id}")
async def update_split(
    split_id: int,
    req: UpdateSplitRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update a Proposed Split's artist list."""
    stmt = select(ProposedSplit).where(ProposedSplit.id == split_id)
    result = await db.execute(stmt)
    split = result.scalar_one_or_none()

    if not split:
        raise HTTPException(status_code=404, detail="Split proposal not found")

    split.proposed_artists = req.proposed_artists
    # Keep status as PENDING so it can be approved separately
    await db.commit()

    return {"message": "Split updated", "proposed_artists": split.proposed_artists}


@router.get("/aliases", response_model=List[ArtistAliasSchema])
async def get_aliases(db: AsyncSession = Depends(get_db)):
    """List all Artist Aliases."""
    stmt = select(ArtistAlias).order_by(ArtistAlias.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


def _revoke_bridge(audit) -> None:
    """Revoke bridge if it exists."""
    if audit.bridge:
        audit.bridge.is_revoked = True


async def _unlink_logs(db: AsyncSession, audit) -> set:
    """Unlink logs and return set of unlinked log IDs."""
    logs_to_unlink = set(audit.log_ids or [])
    if audit.bridge_id and audit.bridge and audit.bridge.work_id:
        stmt = select(BroadcastLog).where(
            BroadcastLog.match_reason == "identity_bridge",
            BroadcastLog.work_id == audit.bridge.work_id,
        )
        res = await db.execute(stmt)
        target_sig = audit.signature
        for log in res.scalars():
            if Normalizer.generate_signature(log.raw_artist, log.raw_title) == target_sig:
                logs_to_unlink.add(log.id)
    if logs_to_unlink:
        await db.execute(
            update(BroadcastLog)
            .where(BroadcastLog.id.in_(logs_to_unlink))
            .values(work_id=None, match_reason=None)
        )
    return logs_to_unlink


async def _recreate_queue_item(db: AsyncSession, audit, logs_to_unlink: set) -> None:
    """Recreate or update DiscoveryQueue item for unlinked logs."""
    if not logs_to_unlink:
        return
    q_stmt = select(DiscoveryQueue).where(DiscoveryQueue.signature == audit.signature)
    queue_item = (await db.execute(q_stmt)).scalar_one_or_none()
    if queue_item:
        queue_item.count += len(logs_to_unlink)
    else:
        db.add(DiscoveryQueue(
            signature=audit.signature,
            raw_artist=audit.raw_artist,
            raw_title=audit.raw_title,
            count=len(logs_to_unlink),
        ))


@router.post("/audit/{audit_id}/undo")
async def undo_verification_action(
    audit_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Undo a verification action (idempotent)."""
    # 1. Fetch original audit entry
    stmt = (
        select(VerificationAudit)
        .where(VerificationAudit.id == audit_id)
        .options(selectinload(VerificationAudit.bridge))
    )
    res = await db.execute(stmt)
    original_audit = res.scalar_one_or_none()

    if not original_audit:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    # 2. Check Idempotency
    if original_audit.is_undone:
        return {
            "status": "success",
            "message": "Already undone",
            "was_already_undone": True
        }

    try:
        _revoke_bridge(original_audit)
        logs_to_unlink = await _unlink_logs(db, original_audit)
        await _recreate_queue_item(db, original_audit, logs_to_unlink)

        # Mark as Undone
        original_audit.is_undone = True
        original_audit.undone_at = datetime.now()

        # E. Create Undo Audit Entry
        undo_audit = VerificationAudit(
            action_type="undo",
            signature=original_audit.signature,
            raw_artist=original_audit.raw_artist,
            raw_title=original_audit.raw_title,
            recording_id=None,
            log_ids=list(logs_to_unlink),
            bridge_id=original_audit.bridge_id,
            performed_by=None # To be filled with user context
        )
        db.add(undo_audit)
        
        await db.commit()
        
        return {
            "status": "success",
            "message": "Action undone",
            "restored_queue_count": len(logs_to_unlink),
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Undo failed: {str(e)}")


@router.get("/audit", response_model=List[VerificationAuditSchema])
async def get_verification_audit(
    skip: int = 0,
    limit: int = 50,
    artist: Optional[str] = None,
    title: Optional[str] = None,
    action_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """List verification audit history with filters."""
    stmt = (
        select(VerificationAudit)
        .options(
            selectinload(VerificationAudit.recording)
            .selectinload(Recording.work)
            .selectinload(Work.artist)
        )
        .order_by(VerificationAudit.created_at.desc())
    )

    if artist:
        stmt = stmt.where(VerificationAudit.raw_artist.ilike(f"%{artist}%"))
    if title:
        stmt = stmt.where(VerificationAudit.raw_title.ilike(f"%{title}%"))
    if action_type:
        stmt = stmt.where(VerificationAudit.action_type == action_type)
    if from_date:
        stmt = stmt.where(VerificationAudit.created_at >= from_date)
    if to_date:
        stmt = stmt.where(VerificationAudit.created_at <= to_date)

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    entries = result.scalars().all()

    # Map to schema
    resp = []
    for e in entries:
        rec_title = None
        rec_artist = None
        if e.recording:
            rec_title = e.recording.title
            if e.recording.work and e.recording.work.artist:
                rec_artist = e.recording.work.artist.name
        
        can_undo = (not e.is_undone) and (e.bridge_id is not None)
        
        resp.append({
            "id": e.id,
            "created_at": e.created_at,
            "action_type": e.action_type,
            "raw_artist": e.raw_artist,
            "raw_title": e.raw_title,
            "recording_title": rec_title,
            "recording_artist": rec_artist,
            "log_count": len(e.log_ids) if e.log_ids else 0,
            "can_undo": can_undo,
            "undone_at": e.undone_at
        })

    return resp
