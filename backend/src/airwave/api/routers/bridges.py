"""Identity Bridge API endpoints.

Phase 4: IdentityBridge links to Work (not Recording). Recording is resolved
at runtime via RecordingResolver based on station context and policies.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import IdentityBridge, Artist, Work

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ArtistSchema(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class WorkSchema(BaseModel):
    id: int
    title: str
    artist: Optional[ArtistSchema] = None
    model_config = ConfigDict(from_attributes=True)


class BridgeResponse(BaseModel):
    """Identity Bridge response schema.
    
    Phase 4: Links to Work (not Recording). Use RecordingResolver to get
    actual recording files when needed.
    """
    id: int
    log_signature: str
    reference_artist: str
    reference_title: str
    work_id: int
    is_revoked: bool
    updated_at: datetime
    created_at: datetime
    work: Optional[WorkSchema] = None
    
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
    # Phase 4: Load work relationship (not recording)
    stmt = select(IdentityBridge).options(
        selectinload(IdentityBridge.work).selectinload(Work.artist)
    )

    if not include_revoked:
        stmt = stmt.where(IdentityBridge.is_revoked == False)

    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.join(IdentityBridge.work).outerjoin(Work.artist).where(
            or_(
                IdentityBridge.reference_artist.ilike(search_pattern),
                IdentityBridge.reference_title.ilike(search_pattern),
                Work.title.ilike(search_pattern),
                Artist.name.ilike(search_pattern)
            )
        )
    
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
    
    # Eager load work relationship for response
    stmt = select(IdentityBridge).where(IdentityBridge.id == bridge_id).options(
        selectinload(IdentityBridge.work).selectinload(Work.artist)
    )
    result = await db.execute(stmt)
    bridge = result.scalar_one()
    
    return bridge
