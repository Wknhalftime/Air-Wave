import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.api.deps import get_db
from airwave.core.cache import cached
from airwave.core.models import (
    Artist,
    BroadcastLog,
    IdentityBridge,
    LibraryFile,
    Recording,
    Station,
    Work,
    WorkArtist,
)
from airwave.core.normalization import Normalizer

from airwave.api.schemas import (
    ArtistDetail,
    ArtistStats,
    RecordingListItem,
    WorkDetail,
    WorkListItem,
)

router = APIRouter()


async def _get_artist_or_404(db: AsyncSession, artist_id: int) -> Artist:
    """Get artist by ID or raise 404."""
    stmt = select(Artist).where(Artist.id == artist_id)
    result = await db.execute(stmt)
    artist = result.scalar_one_or_none()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist


async def _get_work_or_404(db: AsyncSession, work_id: int) -> Work:
    """Get work by ID or raise 404."""
    work = await db.get(Work, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    return work


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


@router.get("/artists/{artist_id}", response_model=ArtistDetail)
@cached(ttl=300, key_prefix="artist_detail")
async def get_artist(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get single artist with aggregated stats.

    Cached for 5 minutes to reduce database load for frequently accessed artists.
    """
    # Query artist with stats
    stmt = (
        select(
            Artist,
            func.count(func.distinct(Work.id)).label("work_count"),
            func.count(func.distinct(Recording.id)).label("rec_count"),
        )
        .outerjoin(Artist.primary_works)
        .outerjoin(Work.recordings)
        .where(Artist.id == artist_id)
        .group_by(Artist.id)
    )

    result = await db.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Artist not found")

    return ArtistDetail(
        id=row.Artist.id,
        name=row.Artist.name,
        musicbrainz_id=row.Artist.musicbrainz_id,
        work_count=row.work_count,
        recording_count=row.rec_count,
    )


@router.get("/artists/{artist_id}/works", response_model=list[WorkListItem])
@cached(ttl=180, key_prefix="artist_works")
async def list_artist_works(
    artist_id: int,
    skip: int = 0,
    limit: int = 24,
    db: AsyncSession = Depends(get_db),
):
    """List works for an artist (via work_artists table for multi-artist support).

    Cached for 3 minutes with pagination parameters in cache key.
    """
    artist = await _get_artist_or_404(db, artist_id)

    # Subquery to get all artist names for each work
    # This is correlated to Work.id and gets ALL artists, not just the filtered one
    all_artists_subquery = (
        select(func.group_concat(Artist.name, ', '))
        .select_from(WorkArtist)
        .join(Artist, WorkArtist.artist_id == Artist.id)
        .where(WorkArtist.work_id == Work.id)
        .correlate(Work)
        .scalar_subquery()
    )

    # Query works via work_artists table to include collaborations
    stmt = (
        select(
            Work.id,
            Work.title,
            all_artists_subquery.label("artist_names"),
            func.count(func.distinct(Recording.id)).label("recording_count"),
            func.sum(Recording.duration).label("duration_total"),
        )
        .join(WorkArtist, Work.id == WorkArtist.work_id)
        .outerjoin(Recording, Work.id == Recording.work_id)
        .where(WorkArtist.artist_id == artist_id)
        .group_by(Work.id, Work.title)
        .order_by(Work.title)
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        WorkListItem(
            id=row.id,
            title=row.title,
            artist_names=row.artist_names or artist.name,  # Fallback to artist name
            recording_count=row.recording_count,
            duration_total=row.duration_total,
            year=None,  # TODO: Add year from first recording if needed
        )
        for row in rows
    ]


@router.get("/works/{work_id}", response_model=WorkDetail)
@cached(ttl=300, key_prefix="work_detail")
async def get_work(
    work_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get single work with artist details.

    Cached for 5 minutes to reduce database load for frequently accessed works.
    """
    # First, get the work with primary artist
    work_stmt = (
        select(Work, Artist.name.label("primary_artist_name"))
        .outerjoin(Artist, Work.artist_id == Artist.id)
        .where(Work.id == work_id)
    )

    work_result = await db.execute(work_stmt)
    work_row = work_result.one_or_none()

    if not work_row:
        raise HTTPException(status_code=404, detail="Work not found")

    work = work_row.Work
    primary_artist_name = work_row.primary_artist_name

    # Get all artist names via work_artists
    artists_stmt = (
        select(func.group_concat(Artist.name, ', ').label("all_artist_names"))
        .select_from(WorkArtist)
        .join(Artist, WorkArtist.artist_id == Artist.id)
        .where(WorkArtist.work_id == work_id)
    )

    artists_result = await db.execute(artists_stmt)
    all_artist_names = artists_result.scalar() or primary_artist_name or "Unknown"

    # Get recording count
    rec_count_stmt = (
        select(func.count(Recording.id))
        .where(Recording.work_id == work_id)
    )
    rec_count_result = await db.execute(rec_count_stmt)
    recording_count = rec_count_result.scalar() or 0

    return WorkDetail(
        id=work.id,
        title=work.title,
        artist_id=work.artist_id,
        artist_name=primary_artist_name,
        artist_names=all_artist_names,
        is_instrumental=work.is_instrumental,
        recording_count=recording_count,
    )


@router.get("/works/{work_id}/recordings", response_model=list[RecordingListItem])
@cached(ttl=120, key_prefix="work_recordings")
async def list_work_recordings(
    work_id: int,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,  # "all", "matched", "unmatched"
    source: Optional[str] = None,  # "all", "library", "metadata"
    db: AsyncSession = Depends(get_db),
):
    """List recordings for a work with optional filters.

    Cached for 2 minutes with pagination and filter parameters in cache key.
    """
    work = await _get_work_or_404(db, work_id)

    # Query recordings with artist names and file status
    # Use subquery to check if recording has files
    has_file_subquery = (
        select(func.count(LibraryFile.id))
        .where(LibraryFile.recording_id == Recording.id)
        .correlate(Recording)
        .scalar_subquery()
    )

    # Subquery to get first file path for filename extraction
    first_file_path_subquery = (
        select(LibraryFile.path)
        .where(LibraryFile.recording_id == Recording.id)
        .order_by(LibraryFile.id)
        .limit(1)
        .correlate(Recording)
        .scalar_subquery()
    )

    stmt = (
        select(
            Recording.id,
            Recording.title,
            Recording.duration,
            Recording.version_type,
            Recording.is_verified,
            Work.title.label("work_title"),
            func.group_concat(Artist.name, ', ').label("artist_names"),
            (has_file_subquery > 0).label("has_file"),
            first_file_path_subquery.label("file_path"),
        )
        .join(Work, Recording.work_id == Work.id)
        .outerjoin(WorkArtist, Work.id == WorkArtist.work_id)
        .outerjoin(Artist, WorkArtist.artist_id == Artist.id)
        .where(Recording.work_id == work_id)
        .group_by(
            Recording.id,
            Recording.title,
            Recording.duration,
            Recording.version_type,
            Recording.is_verified,
            Work.title,
        )
    )

    # Apply filters
    if status == "matched":
        stmt = stmt.where(Recording.is_verified == True)
    elif status == "unmatched":
        stmt = stmt.where(Recording.is_verified == False)

    if source == "library":
        # Only recordings with files
        stmt = stmt.where(has_file_subquery > 0)
    elif source == "metadata":
        # Only recordings without files
        stmt = stmt.where(has_file_subquery == 0)

    stmt = stmt.order_by(Recording.title).offset(skip).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        RecordingListItem(
            id=row.id,
            title=row.title,
            artist_display=row.artist_names or "Unknown",
            duration=row.duration,
            version_type=row.version_type,
            work_title=row.work_title,
            is_verified=row.is_verified,
            has_file=row.has_file,
            filename=os.path.basename(row.file_path) if row.file_path else None,
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
    # Phase 4: Join via work_id (not recording_id)
    stmt = (
        select(
            func.max(BroadcastLog.id).label("id"),
            func.max(BroadcastLog.played_at).label("played_at"),
            func.min(Station.callsign).label("callsign"),
            BroadcastLog.raw_artist,
            BroadcastLog.raw_title,
            func.max(BroadcastLog.match_reason).label("match_reason"),
            BroadcastLog.work_id,
            Artist.name.label("artist_name"),
            Work.title.label("work_title"),
        )
        .join(Station)
        .join(Work, BroadcastLog.work_id == Work.id)
        .join(Artist, Work.artist_id == Artist.id)
        .where(BroadcastLog.work_id.is_not(None))
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
            BroadcastLog.work_id,
            Artist.name,
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
            "track": {  # Keep 'track' key for frontend compatibility
                "id": row.work_id,  # Phase 4: Use work_id
                "artist": row.artist_name,
                "title": row.work_title,
                "path": "N/A",
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
    
    Phase 4: Uses work_id for identity resolution.
    """
    stmt = select(BroadcastLog).where(BroadcastLog.id == log_id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        return {"error": "Log not found"}

    if not log.work_id:
        return {"error": "Log has no work_id to verify"}

    # Phase 4: Fetch Work/Artist directly
    work_stmt = (
        select(Work)
        .options(selectinload(Work.artist))
        .where(Work.id == log.work_id)
    )
    work_res = await db.execute(work_stmt)
    work = work_res.scalar_one()

    if apply_to_artist:
        target_artist_name = work.artist.name

        # Phase 4: Find logs via Work -> Artist
        target_logs_stmt = (
            select(BroadcastLog)
            .join(Work, BroadcastLog.work_id == Work.id)
            .join(Artist, Work.artist_id == Artist.id)
            .where(
                BroadcastLog.raw_artist == log.raw_artist,
                Artist.name == target_artist_name,
                BroadcastLog.match_reason.not_like("%Verified%"),
                BroadcastLog.work_id.is_not(None),
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

            # Phase 4: Create bridge with work_id
            if not existing and target.work_id:
                ib = IdentityBridge(
                    log_signature=sig,
                    reference_artist=target.raw_artist,
                    reference_title=target.raw_title,
                    work_id=target.work_id,
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
    
    Phase 4: Uses work_id for identity resolution.
    """
    stmt = select(BroadcastLog).where(BroadcastLog.id == log_id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        return {"error": "Log not found"}

    if apply_to_artist and log.work_id:
        # Phase 4: Get artist from work directly
        work_stmt = (
            select(Work)
            .options(selectinload(Work.artist))
            .where(Work.id == log.work_id)
        )
        work_res = await db.execute(work_stmt)
        work = work_res.scalar_one()
        target_artist_name = work.artist.name

        # Subquery for Work IDs by this artist
        sub_stmt = (
            select(Work.id)
            .join(Artist)
            .where(Artist.name == target_artist_name)
        )

        # Phase 4: Unlink by setting work_id=None
        unlink_result = await db.execute(
            update(BroadcastLog)
            .where(
                BroadcastLog.raw_artist == log.raw_artist,
                BroadcastLog.work_id.in_(sub_stmt),
            )
            .values(
                work_id=None,
                match_reason="Rejected by User (Batch via Artist)",
            )
        )
        await db.commit()
        return {"status": "rejected", "unlinked_count": unlink_result.rowcount or 0}
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

        # 4. Identity Bridge (Phase 4: links to work, not recording)
        ib = IdentityBridge(
            log_signature=signature,
            reference_artist=log.raw_artist,
            reference_title=log.raw_title,
            work_id=work.id,  # Phase 4: Link to Work
            confidence=1.0,
        )
        db.add(ib)

        # 5. Update Logs (Phase 4: link to work, not recording)
        await db.execute(
            update(BroadcastLog)
            .where(BroadcastLog.raw_artist == log.raw_artist)
            .where(BroadcastLog.raw_title == log.raw_title)
            .values(
                work_id=work.id,
                match_reason="Verified by User (Separate Track)",
            )
        )

    await db.commit()
    # Return new_rec.id
    return {"status": "rejected", "new_track_id": new_rec.id}
