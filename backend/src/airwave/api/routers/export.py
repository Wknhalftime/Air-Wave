import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import BroadcastLog, Recording, Work

router = APIRouter()


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
    
    Args:
        start_date: Start date (YYYY-MM-DD). Defaults to all time.
        end_date: End date (YYYY-MM-DD). Defaults to today.
        station_id: Filter by specific station. Defaults to all stations.
        matched_only: Only export matched logs. Defaults to False.
        unmatched_only: Only export unmatched logs. Defaults to False.
    
    Returns:
        CSV file with columns: Date, Time, Station, Raw Artist, Raw Title,
        Matched Artist, Matched Title, Match Type, Match Confidence
    """
    # Build query
    stmt = (
        select(BroadcastLog)
        .options(
            selectinload(BroadcastLog.station),
            selectinload(BroadcastLog.recording)
            .selectinload(Recording.work)
            .selectinload(Work.artist)
        )
        .order_by(BroadcastLog.played_at.asc())
    )
    
    # Apply filters
    if start_date:
        start_dt = datetime.fromisoformat(f"{start_date}T00:00:00")
        stmt = stmt.where(BroadcastLog.played_at >= start_dt)
    
    if end_date:
        end_dt = datetime.fromisoformat(f"{end_date}T23:59:59")
        stmt = stmt.where(BroadcastLog.played_at <= end_dt)
    
    if station_id:
        stmt = stmt.where(BroadcastLog.station_id == station_id)
    
    if matched_only:
        stmt = stmt.where(BroadcastLog.recording_id.is_not(None))
    
    if unmatched_only:
        stmt = stmt.where(BroadcastLog.recording_id.is_(None))
    
    # Execute query
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
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
    
    # Write data rows
    for log in logs:
        matched_artist = ""
        matched_title = ""
        match_type = log.match_reason or "Unmatched"
        
        if log.recording and log.recording.work:
            if log.recording.work.artist:
                matched_artist = log.recording.work.artist.name
            matched_title = log.recording.title
        
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
    
    # Prepare response
    output.seek(0)
    filename = f"airwave_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
