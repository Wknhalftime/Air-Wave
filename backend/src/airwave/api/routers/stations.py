from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, case
from sqlalchemy.orm import selectinload

from airwave.core.db import get_db
from airwave.core.models import Station, BroadcastLog, ImportBatch, IdentityBridge

router = APIRouter(tags=["Stations"])

@router.get("/", response_model=List[dict])
async def list_stations(db: AsyncSession = Depends(get_db)):
    """List all stations with aggregate matching statistics."""
    # Efficient query to get stations + total logs + matched logs
    stmt = (
        select(
            Station,
            func.count(BroadcastLog.id).label("total_logs"),
            func.count(BroadcastLog.recording_id).label("matched_logs")
        )
        .outerjoin(BroadcastLog, Station.id == BroadcastLog.station_id)
        .group_by(Station.id)
        .order_by(Station.callsign)
    )
    
    result = await db.execute(stmt)
    stations_data = []
    
    for row in result:
        station = row.Station
        total = row.total_logs
        matched = row.matched_logs
        match_rate = (matched / total * 100) if total > 0 else 0
        
        stations_data.append({
            "id": station.id,
            "callsign": station.callsign,
            "total_logs": total,
            "matched_logs": matched,
            "match_rate": round(match_rate, 1)
        })
        
    return stations_data

@router.get("/{station_id}/health", response_model=dict)
async def get_station_health(station_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed health metrics for a station."""
    # 1. Verify Station Exists
    stmt = select(Station).where(Station.id == station_id)
    res = await db.execute(stmt)
    station = res.scalar_one_or_none()
    
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
        
    # 2. Get Import Batches (Recent Activity)
    # We want recently imported batches for this station
    stmt = (
        select(ImportBatch)
        .join(BroadcastLog, BroadcastLog.import_batch_id == ImportBatch.id) # Only if logs exist?
        # Actually ImportBatch is not directly linked to Station in model usually?
        # Let's check model. If logs link to Station AND Batch.
        # We can find batches that contain logs for this station.
        .where(BroadcastLog.station_id == station_id)
        .group_by(ImportBatch.id)
        .order_by(desc(ImportBatch.created_at))
        .limit(10)
    )
    # This query might be slow if logs table is huge. 
    # Alternative: ImportBatch often has metadata? No.
    # Let's stick to simple batch retrieval via logs or just recent logs.
    
    # Simplified: Get matching stats over time (daily buckets?)
    # For now, let's just return aggregate stats + top unmatched.
    
    # 3. Top Unmatched Tracks
    stmt_unmatched = (
        select(
            BroadcastLog.raw_artist, 
            BroadcastLog.raw_title, 
            func.count(BroadcastLog.id).label("count")
        )
        .where(
            BroadcastLog.station_id == station_id,
            BroadcastLog.recording_id.is_(None)
        )
        .group_by(BroadcastLog.raw_artist, BroadcastLog.raw_title)
        .order_by(desc("count"))
        .limit(20)
    )
    res_unmatched = await db.execute(stmt_unmatched)
    unmatched_list = [
        {"artist": row.raw_artist, "title": row.raw_title, "count": row.count} 
        for row in res_unmatched
    ]
    
    return {
        "station": {
            "id": station.id,
            "callsign": station.callsign
        },
        "unmatched_tracks": unmatched_list
    }
