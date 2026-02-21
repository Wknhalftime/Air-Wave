"""Export endpoints for broadcast logs and playlists.

Phase 4: Uses work_id for identity resolution. Recording files are resolved
via RecordingResolver based on station context.
"""

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.config import settings
from airwave.core.models import BroadcastLog, LibraryFile, Recording, Work
from airwave.worker.recording_resolver import RecordingResolver

router = APIRouter()


def _parse_date_range(
    start_date: Optional[str], end_date: Optional[str]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Parse YYYY-MM-DD date strings. Raises HTTPException on invalid format."""
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(f"{start_date}T00:00:00")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date; use YYYY-MM-DD")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(f"{end_date}T23:59:59")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date; use YYYY-MM-DD")
    return start_dt, end_dt


@router.get("/logs")
async def export_logs(
    start_date: Optional[str] = None,  # YYYY-MM-DD
    end_date: Optional[str] = None,    # YYYY-MM-DD
    station_id: Optional[int] = None,
    matched_only: bool = False,        # Filter matched logs
    unmatched_only: bool = False,      # Filter unmatched logs
    db: AsyncSession = Depends(get_db)
):
    """Export broadcast logs as CSV for external music scheduling software.
    
    Phase 4: Uses work_id for identity resolution.
    """
    # Phase 4: Load work relationship (not recording)
    stmt = (
        select(BroadcastLog)
        .options(
            selectinload(BroadcastLog.station),
            selectinload(BroadcastLog.work)
            .selectinload(Work.artist)
        )
        .order_by(BroadcastLog.played_at.asc())
    )
    
    start_dt, end_dt = _parse_date_range(start_date, end_date)
    if start_dt:
        stmt = stmt.where(BroadcastLog.played_at >= start_dt)
    if end_dt:
        stmt = stmt.where(BroadcastLog.played_at <= end_dt)
    
    if station_id:
        stmt = stmt.where(BroadcastLog.station_id == station_id)
    
    # Phase 4: Check by work_id
    if matched_only:
        stmt = stmt.where(BroadcastLog.work_id.is_not(None))
    
    if unmatched_only:
        stmt = stmt.where(BroadcastLog.work_id.is_(None))
    
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "Date",
        "Time",
        "Station",
        "Raw Artist",
        "Raw Title",
        "Matched Artist",
        "Matched Title",
        "Match Type",
        "Match Confidence"
    ])
    
    for log in logs:
        matched_artist = ""
        matched_title = ""
        match_type = log.match_reason or "Unmatched"
        
        # Phase 4: Get info from work
        if log.work:
            if log.work.artist:
                matched_artist = log.work.artist.name
            matched_title = log.work.title
        
        writer.writerow([
            log.played_at.strftime("%Y-%m-%d"),
            log.played_at.strftime("%H:%M:%S"),
            log.station.callsign if log.station else "Unknown",
            log.raw_artist,
            log.raw_title,
            matched_artist,
            matched_title,
            match_type,
            "High" if "Identity Bridge" in match_type else "Medium"
        ])
    
    output.seek(0)
    filename = f"airwave_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/m3u", response_class=Response)
async def export_m3u(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    station_id: Optional[int] = Query(None, description="Filter by station ID"),
    matched_only: bool = Query(True, description="Only include matched logs"),
    db: AsyncSession = Depends(get_db),
):
    """Export matched broadcast logs as an M3U playlist with absolute paths to local library files.

    Phase 4: Uses work_id for identity resolution. Recording files are resolved
    via RecordingResolver based on station context.
    """
    start_dt, end_dt = _parse_date_range(start_date, end_date)

    # Phase 4: Load work relationship, resolve recording at runtime
    stmt = (
        select(BroadcastLog)
        .options(
            selectinload(BroadcastLog.work).selectinload(Work.artist),
        )
        .where(BroadcastLog.work_id.is_not(None))
        .order_by(BroadcastLog.played_at.asc())
    )
    if start_dt is not None:
        stmt = stmt.where(BroadcastLog.played_at >= start_dt)
    if end_dt is not None:
        stmt = stmt.where(BroadcastLog.played_at <= end_dt)
    if station_id is not None:
        stmt = stmt.where(BroadcastLog.station_id == station_id)

    result = await db.execute(stmt)
    logs = result.scalars().all()
    included = 0
    skipped = 0
    lines = ["#EXTM3U"]

    data_dir = Path(settings.DATA_DIR)
    
    # Phase 4: Use RecordingResolver to get the actual recording
    resolver = RecordingResolver(db)

    for log in logs:
        if not log.work_id:
            skipped += 1
            continue
            
        # Resolve recording for this work (using station context if available)
        rec = await resolver.resolve(log.work_id, station_id=log.station_id)
        if not rec:
            logger.warning("No recording found for work_id=%s; skipping log id=%s", log.work_id, log.id)
            skipped += 1
            continue
            
        files = list(rec.files) if rec.files else []
        if not files:
            logger.warning("Recording id=%s has no library files; skipping log id=%s", rec.id, log.id)
            skipped += 1
            continue
            
        first_file: LibraryFile = files[0]
        raw_path = first_file.path
        if not raw_path:
            skipped += 1
            continue
        path_obj = Path(raw_path)
        if not path_obj.is_absolute():
            path_obj = (data_dir / raw_path).resolve()
        abs_path = str(path_obj)

        artist_name = "Unknown"
        if log.work and log.work.artist:
            artist_name = log.work.artist.name
        title = rec.title or "Unknown"
        display = f"{artist_name} - {title}".replace(",", " ")
        duration = int(rec.duration) if rec.duration is not None else -1
        lines.append(f"#EXTINF:{duration},{display}")
        lines.append(abs_path)
        included += 1

    logger.info("M3U export: %s logs queried, %s tracks included, %s skipped", len(logs), included, skipped)
    content = "\n".join(lines)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"airwave_playlist_{timestamp}.m3u"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Airwave-M3U-Included": str(included),
        "X-Airwave-M3U-Skipped": str(skipped),
    }
    return Response(
        content=content,
        media_type="audio/x-mpegurl",
        headers=headers,
    )
