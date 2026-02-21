"""History endpoint for broadcast logs.

Phase 4: Uses work relationship instead of recording.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import BroadcastLog, Work

router = APIRouter()


@router.get("/logs")
async def get_logs(
    station_id: Optional[int] = None,
    date: Optional[str] = None,  # YYYY-MM-DD
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get broadcast logs.
    
    Phase 4: Loads work relationship instead of recording.
    """
    from datetime import timedelta

    # Phase 4: Load work relationship (not recording)
    query = select(BroadcastLog).options(
        selectinload(BroadcastLog.station),
        selectinload(BroadcastLog.work)
        .selectinload(Work.artist),
    )

    # Selection logic:
    # If a specific date is selected, show chronological (ASC) so it reads like a playlist.
    # Otherwise (general recent view), show descending (DESC) to see newest first.
    if date:
        query = query.order_by(BroadcastLog.played_at.asc())
    else:
        query = query.order_by(BroadcastLog.played_at.desc())

    if station_id:
        query = query.where(BroadcastLog.station_id == station_id)

    if date:
        try:
            start_dt = datetime.strptime(date, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=1)
            query = query.where(
                BroadcastLog.played_at >= start_dt,
                BroadcastLog.played_at < end_dt,
            )
        except ValueError:
            pass

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return logs
