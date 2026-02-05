from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.models import (
    Artist,
    BroadcastLog,
    IdentityBridge,
    Recording,
    Station,
    Work,
)
from airwave.core.normalization import Normalizer

from airwave.api.schemas import ArtistStats

router = APIRouter()


@router.get("/artists", response_model=list[ArtistStats])
async def list_artists(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List artists with aggregated stats for grid view."""
    stmt = (
        select(
            Artist,
            func.count(func.distinct(Work.id)).label("work_count"),
            func.count(func.distinct(Recording.id)).label("rec_count"),
        )
        .outerjoin(Artist.primary_works)
        .outerjoin(Work.recordings)
        .group_by(Artist.id)
    )

    if search:
        stmt = stmt.where(Artist.name.ilike(f"%{search}%"))

    stmt = stmt.order_by(Artist.name).offset(skip).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        ArtistStats(
            id=row.Artist.id,
            name=row.Artist.name,
            work_count=row.work_count,
            recording_count=row.rec_count,
            avatar_url=None,
        )
        for row in rows
    ]


@router.get("/tracks")
async def list_tracks(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List recordings with optional search (Joined with Artist/Work)."""
    # Join Recording -> Work -> Artist
    query = select(Recording).options(
        selectinload(Recording.work).selectinload(Work.artist),
        selectinload(Recording.files),
    )

    if search:
        term = f"%{search}%"
        # Join for filtering
        query = (
            query.join(Recording.work)
            .join(Work.artist)
            .where(
                or_(
                    Artist.name.ilike(term),
                    Recording.title.ilike(term),
                    Work.title.ilike(term),
                )
            )
        )

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    recordings = result.scalars().all()

    # Flatten for API response (Backward Compat mostly, but structure changed)
    # Frontend likely expects: id, artist, title, path
    return [
        {
            "id": r.id,
            "title": r.title,  # Version title
            "version_type": r.version_type,
            "artist": r.work.artist.name
            if r.work and r.work.artist
            else "Unknown",
            "work_title": r.work.title if r.work else "Unknown",
            "path": r.files[0].path if r.files else None,
            "duration": r.duration,
        }
        for r in recordings
    ]


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get library statistics."""
    rec_count_stmt = select(func.count(Recording.id))
    station_count_stmt = select(func.count(Station.id))

    rec_res = await db.execute(rec_count_stmt)
    station_res = await db.execute(station_count_stmt)

    return {
        "total_tracks": rec_res.scalar()
        or 0,  # Kept key 'total_tracks' for frontend compat
        "total_stations": station_res.scalar() or 0,
    }


@router.get("/matches/pending")
async def get_pending_matches(
    limit: int = 50, db: AsyncSession = Depends(get_db)
):
    """Get recent matches that might need verification."""
    # We select Log + Recording + Work + Artist info
    stmt = (
        select(
            func.max(BroadcastLog.id).label("id"),
            func.max(BroadcastLog.played_at).label("played_at"),
            func.min(Station.callsign).label("callsign"),
            BroadcastLog.raw_artist,
            BroadcastLog.raw_title,
            func.max(BroadcastLog.match_reason).label("match_reason"),
            BroadcastLog.recording_id,
            Artist.name.label("artist_name"),
            Recording.title.label("recording_title"),
            Work.title.label("work_title"),
        )
        .join(Station)
        .join(Recording, BroadcastLog.recording_id == Recording.id)
        .join(Work, Recording.work_id == Work.id)
        .join(Artist, Work.artist_id == Artist.id)
        .where(BroadcastLog.recording_id.is_not(None))
        .where(BroadcastLog.match_reason.is_not(None))
        .where(BroadcastLog.match_reason.not_like("%Identity Bridge%"))
        .where(BroadcastLog.match_reason.not_like("%Verified by User%"))
        .where(BroadcastLog.match_reason.not_like("%Exact Text Match%"))
        .where(BroadcastLog.match_reason.not_like("%Exact DB Match%"))
        .where(BroadcastLog.match_reason.not_like("%High Confidence Match%"))
        .where(BroadcastLog.match_reason.not_like("%Auto-Promoted Identity%"))
        .group_by(
            BroadcastLog.raw_artist,
            BroadcastLog.raw_title,
            BroadcastLog.recording_id,
            Artist.name,
            Recording.title,
            Work.title,
        )
        .order_by(desc("played_at"))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": row.id,
            "played_at": row.played_at,
            "station": row.callsign,
            "raw_artist": row.raw_artist,
            "raw_title": row.raw_title,
            "match_reason": row.match_reason,
            "track": {  # Keep 'track' key for frontend
                "id": row.recording_id,
                "artist": row.artist_name,
                "title": row.recording_title,  # Or row.work_title if simplified
                "path": "N/A",  # Path is on LibraryFile, excluded for perf or need join
            },
        }
        for row in rows
    ]


@router.post("/matches/{log_id}/verify")
async def verify_match(
    log_id: int,
    apply_to_artist: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Manually verify a match.
    Creates an Identity Bridge entry.
    """
    stmt = select(BroadcastLog).where(BroadcastLog.id == log_id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        return {"error": "Log not found"}

    # Fetch Recording/Work/Artist
    rec_stmt = (
        select(Recording)
        .options(selectinload(Recording.work).selectinload(Work.artist))
        .where(Recording.id == log.recording_id)
    )
    rec_res = await db.execute(rec_stmt)
    recording = rec_res.scalar_one()

    if apply_to_artist:
        target_artist_name = recording.work.artist.name

        # Find all logs with same raw_artist AND matched to a recording by this artist
        target_logs_stmt = (
            select(BroadcastLog)
            .join(Recording)
            .join(Work)
            .join(Artist)
            .where(
                BroadcastLog.raw_artist == log.raw_artist,
                Artist.name == target_artist_name,
                BroadcastLog.match_reason.not_like("%Verified%"),
                BroadcastLog.recording_id.is_not(None),
            )
        )
        target_logs_res = await db.execute(target_logs_stmt)
        target_logs = target_logs_res.scalars().all()
    else:
        target_logs = [log]

    processed_sigs = set()
    raw_pairs = []

    for target in target_logs:
        sig = Normalizer.generate_signature(target.raw_artist, target.raw_title)

        if sig not in processed_sigs:
            raw_pairs.append((target.raw_artist, target.raw_title))
            ib_stmt = select(IdentityBridge).where(
                IdentityBridge.log_signature == sig
            )
            ib_res = await db.execute(ib_stmt)
            existing = ib_res.scalar_one_or_none()

            if not existing and target.recording_id:
                ib = IdentityBridge(
                    log_signature=sig,
                    reference_artist=target.raw_artist,
                    reference_title=target.raw_title,
                    recording_id=target.recording_id,
                    confidence=1.0,
                )
                db.add(ib)
            processed_sigs.add(sig)

        target.match_reason = (
            "Verified by User (Batch)"
            if apply_to_artist
            else "Verified by User"
        )

    if raw_pairs:
        filters = [
            and_(BroadcastLog.raw_artist == a, BroadcastLog.raw_title == t)
            for a, t in raw_pairs
        ]

        await db.execute(
            update(BroadcastLog)
            .where(or_(*filters))
            .where(BroadcastLog.match_reason.not_like("%Verified%"))
            .values(match_reason="Verified by User (Batch)")
        )

    await db.commit()
    return {"status": "verified", "count": len(target_logs)}


@router.post("/matches/{log_id}/reject")
async def reject_match(
    log_id: int,
    apply_to_artist: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Reject a match (Unlink).
    Creates a new Virtual Recording to represent the distinct track.
    """
    stmt = select(BroadcastLog).where(BroadcastLog.id == log_id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        return {"error": "Log not found"}

    if apply_to_artist and log.recording_id:
        rec_stmt = (
            select(Recording)
            .options(selectinload(Recording.work).selectinload(Work.artist))
            .where(Recording.id == log.recording_id)
        )
        rec_res = await db.execute(rec_stmt)
        recording = rec_res.scalar_one()
        target_artist_name = recording.work.artist.name

        # Subquery for Recording IDs by this artist
        sub_stmt = (
            select(Recording.id)
            .join(Work)
            .join(Artist)
            .where(Artist.name == target_artist_name)
        )

        await db.execute(
            update(BroadcastLog)
            .where(
                BroadcastLog.raw_artist == log.raw_artist,
                BroadcastLog.recording_id.in_(sub_stmt),
            )
            .values(
                recording_id=None,
                match_reason="Rejected by User (Batch via Artist)",
            )
        )
    else:
        # Create Virtual Recording
        signature = Normalizer.generate_signature(log.raw_artist, log.raw_title)
        clean_artist = Normalizer.clean(log.raw_artist)
        clean_title = Normalizer.clean(log.raw_title)

        # We need Artist, Work, Recording
        # 1. Artist
        a_stmt = select(Artist).where(Artist.name == clean_artist)
        a_res = await db.execute(a_stmt)
        artist = a_res.scalar_one_or_none()
        if not artist:
            artist = Artist(name=clean_artist)
            db.add(artist)
            await db.flush()

        # 2. Work
        w_stmt = select(Work).where(
            Work.artist_id == artist.id, Work.title == clean_title
        )
        w_res = await db.execute(w_stmt)
        work = w_res.scalar_one_or_none()
        if not work:
            work = Work(title=clean_title, artist_id=artist.id)
            db.add(work)
            await db.flush()

        # 3. Recording (Virtual)
        # Check if exists (by title, ignoring version?)
        # For virtual, we assume title = clean_title, version = None
        r_stmt = select(Recording).where(
            Recording.work_id == work.id, Recording.title == clean_title
        )
        r_res = await db.execute(r_stmt)
        new_rec = r_res.scalar_one_or_none()

        if not new_rec:
            new_rec = Recording(
                work_id=work.id, title=clean_title, version_type="Virtual"
            )
            db.add(new_rec)
            await db.flush()

            # Note: No LibraryFile created for Virtual Recording

        # 4. Identity Bridge
        ib = IdentityBridge(
            log_signature=signature,
            reference_artist=log.raw_artist,
            reference_title=log.raw_title,
            recording_id=new_rec.id,  # New Recording ID
            confidence=1.0,
        )
        db.add(ib)

        # 5. Update Logs
        await db.execute(
            update(BroadcastLog)
            .where(BroadcastLog.raw_artist == log.raw_artist)
            .where(BroadcastLog.raw_title == log.raw_title)
            .values(
                recording_id=new_rec.id,
                match_reason="Verified by User (Separate Track)",
            )
        )

    await db.commit()
    # Return new_rec.id
    return {"status": "rejected", "new_track_id": new_rec.id}
