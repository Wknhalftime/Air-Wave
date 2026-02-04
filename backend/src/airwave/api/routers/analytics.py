from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import Artist, BroadcastLog, Recording, Station, Work

router = APIRouter()


def _categorize_match_reason(reason: str) -> str:
    """Aggregate granular match reasons into high-level categories.

    Args:
        reason: Raw match reason string from BroadcastLog.match_reason

    Returns:
        High-level category string for UI display

    Examples:
        "High Confidence Match (Artist: 95%, ...)" -> "High Confidence"
        "Vector Similarity (Very High: 0.92)" -> "Vector Similarity"
        "Identity Bridge (Exact Match)" -> "Identity Bridge"
    """
    reason_lower = reason.lower()

    if "identity bridge" in reason_lower:
        return "Identity Bridge"
    elif "exact" in reason_lower:
        return "Exact Match"
    elif "high confidence" in reason_lower:
        return "High Confidence"
    elif "vector" in reason_lower and "title" in reason_lower:
        return "Title + Vector"
    elif "vector" in reason_lower:
        return "Vector Similarity"
    elif "verified by user" in reason_lower:
        return "User Verified"
    elif "auto-promoted" in reason_lower:
        return "Auto-Promoted"
    else:
        return "Other"


@router.get("/dashboard")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get high-level dashboard stats."""
    # Total Log Count
    res = await db.execute(select(func.count(BroadcastLog.id)))
    total_plays = res.scalar_one()

    # Active Stations Count
    res_st = await db.execute(select(func.count(Station.id)))
    active_stations = res_st.scalar_one()

    return {"total_plays": total_plays, "active_stations": active_stations}


@router.get("/top-tracks")
async def get_top_tracks(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Get most played recordings."""
    # Aggregation: Group by recording_id
    stmt = (
        select(
            BroadcastLog.recording_id,
            func.count(BroadcastLog.id).label("play_count"),
        )
        .where(BroadcastLog.recording_id.is_not(None))
        .group_by(BroadcastLog.recording_id)
        .order_by(desc("play_count"))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    # Enrich with Recording info
    data = []
    for recording_id, count in rows:
        # Join Rec -> Work -> Artist
        rec_stmt = (
            select(Recording)
            .options(selectinload(Recording.work).selectinload(Work.artist))
            .where(Recording.id == recording_id)
        )

        res = await db.execute(rec_stmt)
        recording = res.scalar_one_or_none()

        if recording and recording.work and recording.work.artist:
            data.append(
                {
                    "name": f"{recording.work.artist.name} - {recording.title}",
                    "artist": recording.work.artist.name,
                    "title": recording.title,
                    "count": count,
                }
            )

    return data


@router.get("/top-artists")
async def get_top_artists(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Get most played artists."""
    # Group by Artist.id via Join
    stmt = (
        select(Artist.name, func.count(BroadcastLog.id).label("play_count"))
        .select_from(BroadcastLog)
        .join(Recording, BroadcastLog.recording_id == Recording.id)
        .join(Work, Recording.work_id == Work.id)
        .join(Artist, Work.artist_id == Artist.id)
        .where(BroadcastLog.recording_id.is_not(None))
        .group_by(Artist.id)
        .order_by(desc("play_count"))
        .limit(limit)
    )

    result = await db.execute(stmt)
    return [{"name": row.name, "count": row.play_count} for row in result]


@router.get("/daily-activity")
async def get_daily_activity(
    days: int = 30, db: AsyncSession = Depends(get_db)
):
    """Get play counts per day."""
    # SQLite specific date truncation: strftime('%Y-%m-%d', played_at)
    stmt = (
        select(
            func.strftime("%Y-%m-%d", BroadcastLog.played_at).label("day"),
            func.count(BroadcastLog.id).label("count"),
        )
        .group_by("day")
        .order_by(desc("day"))
        .limit(days)
    )

    result = await db.execute(stmt)
    data = [{"date": row.day, "count": row.count} for row in result]
    return list(reversed(data))


@router.get("/victory")
async def get_victory_stats(db: AsyncSession = Depends(get_db)):
    """Get comprehensive match rate statistics.
    
    This endpoint quantifies the success of the matching engine by
    breaking down logs by match status and match type.
    """
    # 1. Total Logs
    total_stmt = select(func.count(BroadcastLog.id))
    total_res = await db.execute(total_stmt)
    total_logs = total_res.scalar_one()
    
    # 2. Matched Logs (recording_id is not NULL)
    matched_stmt = select(func.count(BroadcastLog.id)).where(
        BroadcastLog.recording_id.is_not(None)
    )
    matched_res = await db.execute(matched_stmt)
    matched_logs = matched_res.scalar_one()
    
    # 3. Unmatched Logs
    unmatched_logs = total_logs - matched_logs
    
    # 4. Match Rate Percentage
    match_rate = (matched_logs / total_logs * 100) if total_logs > 0 else 0
    
    # 5. Breakdown by Match Reason (for pie chart)
    # Aggregate granular match reasons into high-level categories
    breakdown_stmt = (
        select(
            BroadcastLog.match_reason,
            func.count(BroadcastLog.id).label("count")
        )
        .where(BroadcastLog.match_reason.is_not(None))
        .group_by(BroadcastLog.match_reason)
    )
    breakdown_res = await db.execute(breakdown_stmt)

    # Aggregate into categories
    category_counts = {}
    for row in breakdown_res:
        reason = row.match_reason
        category = _categorize_match_reason(reason)
        category_counts[category] = (
            category_counts.get(category, 0) + row.count
        )

    # Sort by count descending
    breakdown = [
        {"type": category, "count": count}
        for category, count in sorted(
            category_counts.items(), key=lambda x: x[1], reverse=True
        )
    ]
    
    # 6. Verified vs Auto-Matched
    verified_stmt = select(func.count(BroadcastLog.id)).where(
        BroadcastLog.match_reason.like("%Verified by User%")
    )
    verified_res = await db.execute(verified_stmt)
    verified_count = verified_res.scalar_one()
    
    auto_matched_count = matched_logs - verified_count
    
    # 7. Identity Bridge Usage
    bridge_stmt = select(func.count(BroadcastLog.id)).where(
        BroadcastLog.match_reason.like("%Identity Bridge%")
    )
    bridge_res = await db.execute(bridge_stmt)
    bridge_count = bridge_res.scalar_one()
    
    return {
        "total_logs": total_logs,
        "matched_logs": matched_logs,
        "unmatched_logs": unmatched_logs,
        "match_rate": round(match_rate, 2),
        "verified_count": verified_count,
        "auto_matched_count": auto_matched_count,
        "bridge_count": bridge_count,
        "breakdown": breakdown,
        "summary": {
            "identity_bridge": bridge_count,
            "user_verified": verified_count,
            "auto_matched": auto_matched_count - bridge_count,
            "unmatched": unmatched_logs
        }
    }
