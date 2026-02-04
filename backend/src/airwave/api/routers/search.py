from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import (
    Artist,
    BroadcastLog,
    Recording,
    Station,
    Work,
)

router = APIRouter()


class SearchResultTrack(BaseModel):
    id: int
    artist: str
    title: str
    album: Optional[str] = None  # Deprecated/Empty for now
    path: Optional[str] = None
    type: Literal["track"] = "track"


class SearchResultLog(BaseModel):
    id: int
    played_at: datetime
    raw_artist: str
    raw_title: str
    station_callsign: str
    match_reason: Optional[str]
    track_id: Optional[int]  # Actually recording_id
    type: Literal["log"] = "log"


class SearchResponse(BaseModel):
    tracks: List[SearchResultTrack] = []
    logs: List[SearchResultLog] = []


@router.get("/", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=2),
    type: Literal["all", "track", "log"] = "all",
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Universal Search Endpoint.
    Searches Recordings (Library) and BroadcastLogs (History).
    """
    response = SearchResponse()
    term = f"%{q}%"

    # Search Tracks (Recordings)
    if type in ["all", "track"]:
        # Join Recording -> Work -> Artist
        stmt = (
            select(Recording)
            .options(
                selectinload(Recording.work).selectinload(Work.artist),
                selectinload(Recording.files),
            )
            .join(Recording.work)
            .join(Work.artist)
            .where(
                or_(
                    Artist.name.ilike(term),
                    Recording.title.ilike(term),
                    Work.title.ilike(term),
                )
            )
            .limit(limit)
        )

        result = await db.execute(stmt)
        recordings = result.scalars().all()

        response.tracks = [
            SearchResultTrack(
                id=r.id,
                artist=r.work.artist.name
                if r.work and r.work.artist
                else "Unknown",
                title=r.title,  # Version title
                album=None,
                path=r.files[0].path if r.files else None,
            )
            for r in recordings
        ]

    # Search Logs
    if type in ["all", "log"]:
        # Join Station to get callsign
        stmt = (
            select(BroadcastLog, Station.callsign)
            .join(Station)
            .where(
                or_(
                    BroadcastLog.raw_artist.ilike(term),
                    BroadcastLog.raw_title.ilike(term),
                )
            )
            .order_by(desc(BroadcastLog.played_at))
            .limit(limit)
        )

        result = await db.execute(stmt)
        rows = result.all()

        response.logs = [
            SearchResultLog(
                id=row.BroadcastLog.id,
                played_at=row.BroadcastLog.played_at,
                raw_artist=row.BroadcastLog.raw_artist,
                raw_title=row.BroadcastLog.raw_title,
                station_callsign=row.callsign,
                match_reason=row.BroadcastLog.match_reason,
                track_id=row.BroadcastLog.recording_id,  # Mapping recording_id to track_id field
            )
            for row in rows
        ]

    return response
