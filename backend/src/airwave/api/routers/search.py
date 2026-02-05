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
    BroadcastLog,
    Recording,
    Station,
    Work,
    LibraryFile,
)
from airwave.core.normalization import Normalizer

router = APIRouter()


class SearchResultTrack(BaseModel):
    id: int
    artist: str
    title: str
    album: Optional[str] = None  # Deprecated/Empty for now
    album: Optional[str] = None  # Deprecated/Empty for now
    path: Optional[str] = None
    status: Literal["Gold", "Silver", "Bronze"]
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
    include_bronze: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Universal Search Endpoint.
    Searches Recordings (Library) and BroadcastLogs (History).
    """
    response = SearchResponse()

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
            .outerjoin(LibraryFile, Recording.id == LibraryFile.recording_id) # Explicit join for filtering
        )
        
        # Multi-term search: normalize query, split into words, and require ALL words to match
        # Normalization handles accents, special characters, brackets, and remaster tags
        # Each word can match in artist name, recording title, or work title
        normalized_query = Normalizer.clean(q)
        terms = normalized_query.split()
        for word in terms:
            word_pattern = f"%{word}%"
            stmt = stmt.where(
                or_(
                    Artist.name.ilike(word_pattern),
                    Recording.title.ilike(word_pattern),
                    Work.title.ilike(word_pattern),
                )
            )

        if not include_bronze:
            # Bronze = Unverified AND No File.
            # So Keep = Verified OR Has File.
            stmt = stmt.where(
                or_(
                    Recording.is_verified == True,
                    LibraryFile.id.is_not(None)
                )
            )
        
        # distinct() because matched multiple files/search terms could dupe
        stmt = stmt.distinct()
        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        recordings = result.scalars().all()

        response.tracks = []
        for r in recordings:
            # Determine Status
            has_file = bool(r.files)
            if has_file:
                status = "Gold"
            elif r.is_verified:
                status = "Silver"
            else:
                status = "Bronze"
            
            response.tracks.append(
                SearchResultTrack(
                    id=r.id,
                    artist=r.work.artist.name if r.work and r.work.artist else "Unknown",
                    title=r.title,
                    album=None,
                    path=r.files[0].path if r.files else None,
                    status=status
                )
            )

    # Search Logs
    if type in ["all", "log"]:
        # Normalize query for consistent searching
        normalized_query = Normalizer.clean(q)
        terms = normalized_query.split()

        # Join Station to get callsign
        stmt = (
            select(BroadcastLog, Station.callsign)
            .join(Station)
            .order_by(desc(BroadcastLog.played_at))
            .limit(limit)
        )

        # Apply multi-term search (all words must match)
        for word in terms:
            word_pattern = f"%{word}%"
            stmt = stmt.where(
                or_(
                    BroadcastLog.raw_artist.ilike(word_pattern),
                    BroadcastLog.raw_title.ilike(word_pattern),
                )
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
