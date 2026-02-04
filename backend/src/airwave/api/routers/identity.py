from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import (
    Artist,
    ArtistAlias,
    BroadcastLog,
    IdentityBridge,
    ProposedSplit,
    Recording,
    Work,
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


class CreateBridgeRequest(BaseModel):
    raw_artist: str
    raw_title: str
    recording_id: int


class CreateAliasRequest(BaseModel):
    raw_name: str
    resolved_name: str


@router.get("/bridges", response_model=List[IdentityBridgeSchema])
async def get_bridges(
    skip: int = 0,
    limit: int = 50,
    term: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all Identity Bridge entries with optional search."""
    stmt = (
        select(IdentityBridge)
        .options(
            selectinload(IdentityBridge.recording)
            .selectinload(Recording.work)
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

    # Pydantic schemas expect attributes to be accessible.
    # We map manually to ensure structure matches IdentityBridgeSchema
    resp = []
    for b in bridges:
        artist_name = "Unknown"
        if b.recording and b.recording.work and b.recording.work.artist:
            artist_name = b.recording.work.artist.name
            
        resp.append({
            "id": b.id,
            "raw_artist": b.reference_artist,
            "raw_title": b.reference_title,
            "recording": {
                "id": b.recording_id,
                "title": b.recording.title if b.recording else "Unknown",
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
    
    # Check if any logs are using this bridge (by recording_id + signature implied match)
    # Actually, we check if logs matched via "Identity Bridge" to this recording exist.
    # A bit loose but gives a warning count.
    log_stmt = select(func.count(BroadcastLog.id)).where(
        BroadcastLog.match_reason.like("%Identity Bridge%"),
        BroadcastLog.recording_id == bridge.recording_id
    )
    log_count = await db.execute(log_stmt)
    count = log_count.scalar() or 0
    
    await db.delete(bridge)
    await db.commit()
    
    return {
        "message": "Bridge deleted",
        "affected_logs": count,
        "warning": "Affected logs will need re-matching"
    }


@router.post("/bridges")
async def create_bridge(
    req: CreateBridgeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Manually create an Identity Bridge (Teach the AI)."""
    
    # Verify recording exists
    rec_stmt = select(Recording).where(Recording.id == req.recording_id)
    rec_res = await db.execute(rec_stmt)
    recording = rec_res.scalar_one_or_none()
    
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
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
    
    # Create bridge
    bridge = IdentityBridge(
        log_signature=signature,
        reference_artist=req.raw_artist,
        reference_title=req.raw_title,
        recording_id=req.recording_id,
        confidence=1.0
    )
    db.add(bridge)
    await db.commit()
    
    return {"message": "Bridge created", "id": bridge.id}


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

    # Join the proposed artists for the alias map (e.g. "Artist A & Artist B")
    resolved_name = " & ".join(split.proposed_artists)

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


@router.get("/aliases", response_model=List[ArtistAliasSchema])
async def get_aliases(db: AsyncSession = Depends(get_db)):
    stmt = select(ArtistAlias).order_by(ArtistAlias.updated_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
