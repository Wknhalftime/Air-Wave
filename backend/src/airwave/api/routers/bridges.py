from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import IdentityBridge, Recording, Artist, Work

from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ArtistSchema(BaseModel):
    name: str
    model_config = ConfigDict(from_attributes=True)

class WorkSchema(BaseModel):
    artist: Optional[ArtistSchema] = None
    model_config = ConfigDict(from_attributes=True)

class RecordingSchema(BaseModel):
    title: str
    work: Optional[WorkSchema] = None
    model_config = ConfigDict(from_attributes=True)

class BridgeResponse(BaseModel):
    id: int
    log_signature: str
    reference_artist: str
    reference_title: str
    recording_id: int
    is_revoked: bool
    updated_at: datetime
    created_at: datetime
    recording: Optional[RecordingSchema] = None
    
    model_config = ConfigDict(from_attributes=True)

router = APIRouter()

@router.get("/", response_model=List[BridgeResponse])
async def list_bridges(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    include_revoked: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List identity bridges with pagination and search."""
    stmt = select(IdentityBridge).options(
        selectinload(IdentityBridge.recording).selectinload(Recording.work).selectinload(Work.artist)
    )

    if not include_revoked:
        stmt = stmt.where(IdentityBridge.is_revoked == False)

    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.join(IdentityBridge.recording).outerjoin(Recording.work).outerjoin(Work.artist).where(
            or_(
                IdentityBridge.reference_artist.ilike(search_pattern),
                IdentityBridge.reference_title.ilike(search_pattern),
                Recording.title.ilike(search_pattern),
                Artist.name.ilike(search_pattern)
            )
        )

    # Count total
    # Note: For strict pagination in production, a separate count query is better
    # but for simplicity/mvp we might just fetch and slice, or do two queries.
    # Let's do two queries for proper metadata.
    
    # ... actually, let's keep it simple for now and rely on client infinite scroll or simple paging
    # We'll return a simple list and let client handle "no more results" by empty list.
    
    stmt = stmt.order_by(desc(IdentityBridge.updated_at))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    bridges = result.scalars().all()

    return bridges

@router.patch("/{bridge_id}", response_model=BridgeResponse)
async def update_bridge_status(
    bridge_id: int,
    is_revoked: bool,
    db: AsyncSession = Depends(get_db),
):
    """Update the revoked status of a bridge."""
    bridge = await db.get(IdentityBridge, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="Bridge not found")

    bridge.is_revoked = is_revoked
    await db.commit()
    await db.refresh(bridge)
    
    # Eager load relationships for response
    # We need to reload with options or just return the bridge and let pydantic handle missing relations if optional
    # But BridgeResponse expects recording.
    # Let's eager load.
    stmt = select(IdentityBridge).where(IdentityBridge.id == bridge_id).options(
        selectinload(IdentityBridge.recording).selectinload(Recording.work).selectinload(Work.artist)
    )
    result = await db.execute(stmt)
    bridge = result.scalar_one()
    
    return bridge
