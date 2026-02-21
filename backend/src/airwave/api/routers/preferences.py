"""API endpoints for managing recording preferences (Policy Layer).

This module provides CRUD endpoints for:
- Station preferences: Station-specific recording preferences
- Format preferences: Format-based recording preferences (AC, CHR, ROCK, etc.)
- Work defaults: Global default recordings for works
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import (
    FormatPreference,
    Recording,
    Station,
    StationPreference,
    Work,
    WorkDefaultRecording,
)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class RecordingInfo(BaseModel):
    """Brief recording info for preference responses."""

    id: int
    title: str
    version_type: Optional[str] = None

    model_config = {"from_attributes": True}


class WorkInfo(BaseModel):
    """Brief work info for preference responses."""

    id: int
    title: str

    model_config = {"from_attributes": True}


class StationInfo(BaseModel):
    """Brief station info for preference responses."""

    id: int
    callsign: str
    format_code: Optional[str] = None

    model_config = {"from_attributes": True}


# Station Preference Schemas
class StationPreferenceCreate(BaseModel):
    """Request body for creating a station preference."""

    station_id: int
    work_id: int
    preferred_recording_id: int
    priority: int = 0


class StationPreferenceResponse(BaseModel):
    """Response for a station preference."""

    id: int
    station_id: int
    work_id: int
    preferred_recording_id: int
    priority: int
    station: Optional[StationInfo] = None
    work: Optional[WorkInfo] = None
    preferred_recording: Optional[RecordingInfo] = None

    model_config = {"from_attributes": True}


# Format Preference Schemas
class FormatPreferenceCreate(BaseModel):
    """Request body for creating a format preference."""

    format_code: str
    work_id: int
    preferred_recording_id: int
    exclude_tags: List[str] = []
    priority: int = 0


class FormatPreferenceResponse(BaseModel):
    """Response for a format preference."""

    id: int
    format_code: str
    work_id: int
    preferred_recording_id: int
    exclude_tags: List[str]
    priority: int
    work: Optional[WorkInfo] = None
    preferred_recording: Optional[RecordingInfo] = None

    model_config = {"from_attributes": True}


# Work Default Schemas
class WorkDefaultCreate(BaseModel):
    """Request body for creating/updating a work default recording."""

    work_id: int
    default_recording_id: int


class WorkDefaultResponse(BaseModel):
    """Response for a work default recording."""

    work_id: int
    default_recording_id: int
    work: Optional[WorkInfo] = None
    default_recording: Optional[RecordingInfo] = None

    model_config = {"from_attributes": True}


# =============================================================================
# Validation Helpers
# =============================================================================


async def _validate_recording_for_work(
    db: AsyncSession,
    recording_id: int,
    work_id: int,
) -> Recording:
    """Validate recording exists and belongs to work. Returns Recording or raises HTTPException."""
    recording = await db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recording {recording_id} not found",
        )
    if recording.work_id != work_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recording {recording_id} does not belong to work {work_id}",
        )
    return recording


# =============================================================================
# Station Preference Endpoints
# =============================================================================


@router.get("/stations", response_model=List[StationPreferenceResponse])
async def list_station_preferences(
    station_id: Optional[int] = None,
    work_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """List station preferences, optionally filtered by station or work."""
    stmt = select(StationPreference).options(
        selectinload(StationPreference.station),
        selectinload(StationPreference.work),
        selectinload(StationPreference.preferred_recording),
    )

    if station_id:
        stmt = stmt.where(StationPreference.station_id == station_id)
    if work_id:
        stmt = stmt.where(StationPreference.work_id == work_id)

    stmt = stmt.order_by(StationPreference.station_id, StationPreference.priority)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/stations",
    response_model=StationPreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_station_preference(
    data: StationPreferenceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new station preference."""
    # Validate station exists
    station = await db.get(Station, data.station_id)
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station {data.station_id} not found",
        )

    # Validate work exists
    work = await db.get(Work, data.work_id)
    if not work:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work {data.work_id} not found",
        )

    await _validate_recording_for_work(
        db, data.preferred_recording_id, data.work_id
    )

    pref = StationPreference(
        station_id=data.station_id,
        work_id=data.work_id,
        preferred_recording_id=data.preferred_recording_id,
        priority=data.priority,
    )
    db.add(pref)
    await db.commit()
    await db.refresh(pref)

    # Load relationships for response
    stmt = (
        select(StationPreference)
        .where(StationPreference.id == pref.id)
        .options(
            selectinload(StationPreference.station),
            selectinload(StationPreference.work),
            selectinload(StationPreference.preferred_recording),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one()


@router.delete("/stations/{preference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_station_preference(
    preference_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a station preference."""
    pref = await db.get(StationPreference, preference_id)
    if not pref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station preference {preference_id} not found",
        )

    await db.delete(pref)
    await db.commit()


# =============================================================================
# Format Preference Endpoints
# =============================================================================


@router.get("/formats", response_model=List[FormatPreferenceResponse])
async def list_format_preferences(
    format_code: Optional[str] = None,
    work_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """List format preferences, optionally filtered by format code or work."""
    stmt = select(FormatPreference).options(
        selectinload(FormatPreference.work),
        selectinload(FormatPreference.preferred_recording),
    )

    if format_code:
        stmt = stmt.where(FormatPreference.format_code == format_code)
    if work_id:
        stmt = stmt.where(FormatPreference.work_id == work_id)

    stmt = stmt.order_by(FormatPreference.format_code, FormatPreference.priority)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/formats",
    response_model=FormatPreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_format_preference(
    data: FormatPreferenceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new format preference."""
    work = await db.get(Work, data.work_id)
    if not work:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work {data.work_id} not found",
        )

    await _validate_recording_for_work(
        db, data.preferred_recording_id, data.work_id
    )

    pref = FormatPreference(
        format_code=data.format_code.upper(),
        work_id=data.work_id,
        preferred_recording_id=data.preferred_recording_id,
        exclude_tags=data.exclude_tags,
        priority=data.priority,
    )
    db.add(pref)
    await db.commit()
    await db.refresh(pref)

    # Load relationships for response
    stmt = (
        select(FormatPreference)
        .where(FormatPreference.id == pref.id)
        .options(
            selectinload(FormatPreference.work),
            selectinload(FormatPreference.preferred_recording),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one()


@router.delete("/formats/{preference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_format_preference(
    preference_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a format preference."""
    pref = await db.get(FormatPreference, preference_id)
    if not pref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Format preference {preference_id} not found",
        )

    await db.delete(pref)
    await db.commit()


# =============================================================================
# Work Default Endpoints
# =============================================================================


@router.get("/defaults", response_model=List[WorkDefaultResponse])
async def list_work_defaults(
    work_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """List work default recordings, optionally filtered by work."""
    stmt = select(WorkDefaultRecording).options(
        selectinload(WorkDefaultRecording.work),
        selectinload(WorkDefaultRecording.default_recording),
    )

    if work_id:
        stmt = stmt.where(WorkDefaultRecording.work_id == work_id)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/defaults",
    response_model=WorkDefaultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_update_work_default(
    data: WorkDefaultCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create or update a work's default recording.

    Since each work can only have one default, this will update if one exists.
    """
    work = await db.get(Work, data.work_id)
    if not work:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work {data.work_id} not found",
        )

    await _validate_recording_for_work(
        db, data.default_recording_id, data.work_id
    )

    # Check if default already exists
    existing = await db.get(WorkDefaultRecording, data.work_id)
    if existing:
        existing.default_recording_id = data.default_recording_id
        await db.commit()
        await db.refresh(existing)
        work_default = existing
    else:
        work_default = WorkDefaultRecording(
            work_id=data.work_id,
            default_recording_id=data.default_recording_id,
        )
        db.add(work_default)
        await db.commit()
        await db.refresh(work_default)

    # Load relationships for response
    stmt = (
        select(WorkDefaultRecording)
        .where(WorkDefaultRecording.work_id == work_default.work_id)
        .options(
            selectinload(WorkDefaultRecording.work),
            selectinload(WorkDefaultRecording.default_recording),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one()


@router.delete("/defaults/{work_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_default(
    work_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a work's default recording."""
    work_default = await db.get(WorkDefaultRecording, work_id)
    if not work_default:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work default for work {work_id} not found",
        )

    await db.delete(work_default)
    await db.commit()


# =============================================================================
# Utility Endpoints
# =============================================================================


@router.get("/formats/codes", response_model=List[str])
async def list_format_codes(db: AsyncSession = Depends(get_db)):
    """List all distinct format codes in use."""
    # Get from format preferences
    stmt1 = select(FormatPreference.format_code).distinct()
    result1 = await db.execute(stmt1)
    pref_codes = set(result1.scalars().all())

    # Get from stations
    stmt2 = select(Station.format_code).where(Station.format_code.isnot(None)).distinct()
    result2 = await db.execute(stmt2)
    station_codes = set(result2.scalars().all())

    # Combine and sort
    all_codes = sorted(pref_codes | station_codes)
    return all_codes
