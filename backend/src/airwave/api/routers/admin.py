import asyncio
import json
import os
import shutil
import uuid
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.api.deps import get_db
from airwave.core.models import Album, Artist, Recording, SystemSetting, Work, WorkArtist
from airwave.core.task_store import (
    cancel_task,
    complete_task,
    create_task,
    get_task,
    update_progress,
    update_total,
)
from airwave.worker.main import (
    run_bulk_import,
    run_discovery_task,
    run_import,
    run_reindex,
    run_scan,
    run_sync_files,
)

router = APIRouter()


class Setting(BaseModel):
    key: str
    value: str
    description: Optional[str] = None



class ScanRequest(BaseModel):
    path: Optional[str] = None


class SetMusicBrainzIdRequest(BaseModel):
    musicbrainz_id: Optional[str] = None  # UUID string or null to clear


class MergeArtistsRequest(BaseModel):
    source_artist_id: int  # Artist to merge from (will be removed)
    target_artist_id: int  # Artist to merge into (kept)


class MergeWorksRequest(BaseModel):
    source_work_id: int  # Work to merge from (will be removed)
    target_work_id: int  # Work to merge into (kept)


@router.get("/pipeline-stats")
async def get_pipeline_stats(session: AsyncSession = Depends(get_db)):
    """Get stats for the mission control pipeline."""
    from sqlalchemy import func, select

    from airwave.core.models import BroadcastLog, DiscoveryQueue, Recording

    # Total Logs
    res = await session.execute(select(func.count(BroadcastLog.id)))
    total_logs = res.scalar() or 0

    # Unmatched (Phase 4: check by work_id)
    res = await session.execute(
        select(func.count(BroadcastLog.id)).where(BroadcastLog.work_id.is_(None))
    )
    unmatched_logs = res.scalar() or 0

    # Discovery Queue
    res = await session.execute(select(func.count(DiscoveryQueue.signature)))
    discovery_count = res.scalar() or 0

    # Verified Library (Tracks)
    res = await session.execute(select(func.count(Recording.id)))
    total_tracks = res.scalar() or 0

    return {
        "total_logs": total_logs,
        "unmatched_logs": unmatched_logs,
        "discovery_queue": discovery_count,
        "total_tracks": total_tracks,
    }


@router.get("/settings", response_model=List[Setting])
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Get all system settings."""
    result = await db.execute(select(SystemSetting))
    settings = result.scalars().all()

    # Defaults if missing
    defaults = {"music_dir": "D:\\Media\\Music", "acoustid_key": ""}

    current_keys = {s.key for s in settings}
    for key, val in defaults.items():
        if key not in current_keys:
            # We don't save defaults to DB automatically here to avoid read-only confusion,
            # but for UI it helps to show them.
            # Actually, let's return combined list.
            pass

    # Return what is in DB. Frontend can handle defaults for "Import Path".
    return settings


@router.post("/settings")
async def update_setting(setting: Setting, db: AsyncSession = Depends(get_db)):
    """Update or Create a setting."""
    stmt = select(SystemSetting).where(SystemSetting.key == setting.key)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = setting.value
        existing.description = setting.description or existing.description
    else:
        new_setting = SystemSetting(
            key=setting.key,
            value=setting.value,
            description=setting.description,
        )
        db.add(new_setting)

    await db.commit()
    return {"status": "ok"}


@router.post("/reindex")
async def reindex_vector_db(
    background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_db)
):
    """Rebuild VectorDB from Tracks."""
    background_tasks.add_task(run_reindex)
    return {"message": "Reindex started in background"}


def _create_and_dispatch_task(
    background_tasks: BackgroundTasks,
    task_type: str,
    runner_fn,
    message: str = "Initializing...",
    *args,
) -> str:
    """Create a task in TaskStore and dispatch it in the background."""
    task_id = str(uuid.uuid4())
    create_task(task_id, task_type, 1)
    update_progress(task_id, 0, message)
    background_tasks.add_task(runner_fn, *args, task_id)
    return task_id


@router.post("/scan")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    req: ScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a file sync scan with progress tracking."""
    path = req.path
    if not path:
        stmt = select(SystemSetting).where(SystemSetting.key == "music_dir")
        result = await db.execute(stmt)
        setting = result.scalar_one_or_none()
        path = setting.value if setting else "D:\\Media\\Music"

    task_id = _create_and_dispatch_task(
        background_tasks, "sync", run_sync_files, "Initializing scan...", path
    )
    return {"status": "started", "path": path, "task_id": task_id}


@router.post("/trigger-scan")
async def trigger_internal_scan(background_tasks: BackgroundTasks):
    """Trigger the 'scan' command (Log -> Library promotion) with progress tracking."""
    task_id = _create_and_dispatch_task(
        background_tasks, "scan", run_scan, "Initializing scan..."
    )
    return {"status": "started", "task_id": task_id}


@router.post("/trigger-discovery")
async def trigger_discovery(background_tasks: BackgroundTasks):
    """Rebuild the DiscoveryQueue from unmatched logs with progress tracking."""
    task_id = _create_and_dispatch_task(
        background_tasks, "discovery", run_discovery_task, "Initializing discovery..."
    )
    return {"status": "started", "task_id": task_id}


@router.post("/import-folder")
async def import_folder(background_tasks: BackgroundTasks, req: ScanRequest):
    """Trigger a recursive bulk import from a folder."""
    logger.info(f"Bulk import request received: {req}")

    path = req.path
    if not path:
        logger.error("Bulk import failed: Path is required")
        raise HTTPException(status_code=400, detail="Path is required")

    # Verify path exists
    if not os.path.exists(path):
        logger.error(f"Bulk import failed: Path does not exist: {path}")
        raise HTTPException(
            status_code=400, detail=f"Path does not exist on server: {path}"
        )

    logger.info(f"Starting bulk import from: {path}")
    task_id = _create_and_dispatch_task(
        background_tasks, "import", run_bulk_import,
        f"Initializing import for {path}...", path
    )
    return {"status": "started", "path": path, "task_id": task_id}


@router.post("/import")
async def upload_import(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
):
    """Upload a CSV and import it with progress tracking."""
    # Save to temp
    upload_dir = "data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    task_id = _create_and_dispatch_task(
        background_tasks, "import", run_import, "Starting import...", file_path
    )
    return {"status": "started", "filename": file.filename, "task_id": task_id}


@router.get("/tasks/{task_id}/stream")
async def stream_task_progress(task_id: str):
    """Server-Sent Events endpoint for real-time task progress.
    Returns a stream of JSON updates every 500ms until the task completes.
    """

    async def event_generator():
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'connected': True})}\n\n"

            while True:
                task = get_task(task_id)

                if not task:
                    yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                    break

                # Manually serialize to handle datetime objects
                task_dict = {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "status": task.status,
                    "progress": task.progress,
                    "current": task.current,
                    "total": task.total,
                    "message": task.message,
                    "started_at": task.started_at.isoformat()
                    if task.started_at
                    else None,
                    "completed_at": task.completed_at.isoformat()
                    if task.completed_at
                    else None,
                    "error": task.error,
                }
                yield f"data: {json.dumps(task_dict)}\n\n"

                # Stop if task is complete
                if task.status in ["completed", "failed", "cancelled"]:
                    break

                # Wait before next update
                await asyncio.sleep(0.5)  # 500ms updates
        except Exception as e:
            # Log the error and send it to client
            logger.error(f"SSE error for task {task_id}: {e}")
            import traceback

            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task.

    Args:
        task_id: The ID of the task to cancel

    Returns:
        Status of the cancellation request
    """
    success = cancel_task(task_id)

    if success:
        logger.info(f"Cancellation requested for task {task_id}")
        return {"status": "cancellation_requested", "task_id": task_id}
    else:
        task = get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        else:
            return {
                "status": "already_completed",
                "task_id": task_id,
                "task_status": task.status
            }


@router.patch("/artists/{artist_id}/musicbrainz-id")
async def set_artist_musicbrainz_id(
    artist_id: int,
    body: SetMusicBrainzIdRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set or clear the MusicBrainz Artist ID for an artist."""
    res = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = res.scalar_one_or_none()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    if body.musicbrainz_id is not None and body.musicbrainz_id.strip() == "":
        body.musicbrainz_id = None
    if body.musicbrainz_id is not None:
        existing_res = await db.execute(
            select(Artist).where(
                Artist.musicbrainz_id == body.musicbrainz_id,
                Artist.id != artist_id,
            )
        )
        if existing_res.scalars().first():
            raise HTTPException(
                status_code=409,
                detail="Another artist already has this MusicBrainz ID",
            )
    artist.musicbrainz_id = body.musicbrainz_id
    await db.commit()
    await db.refresh(artist)
    return {"artist_id": artist_id, "musicbrainz_id": artist.musicbrainz_id}


@router.post("/artists/merge")
async def merge_artists(
    body: MergeArtistsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Merge source artist into target artist (repoint FKs, then delete source)."""
    if body.source_artist_id == body.target_artist_id:
        raise HTTPException(
            status_code=400, detail="Source and target artist must differ"
        )
    res = await db.execute(
        select(Artist).where(Artist.id.in_([body.source_artist_id, body.target_artist_id]))
    )
    artists = {a.id: a for a in res.scalars().all()}
    source = artists.get(body.source_artist_id)
    target = artists.get(body.target_artist_id)
    if not source or not target:
        raise HTTPException(status_code=404, detail="Artist not found")

    # Repoint Work.artist_id
    await db.execute(
        update(Work).where(Work.artist_id == body.source_artist_id).values(artist_id=body.target_artist_id)
    )
    # Repoint Album.artist_id
    await db.execute(
        update(Album).where(Album.artist_id == body.source_artist_id).values(artist_id=body.target_artist_id)
    )
    # WorkArtist: for each (work_id, source_id), either update to target or delete if (work_id, target_id) exists
    res_wa = await db.execute(
        select(WorkArtist).where(WorkArtist.artist_id == body.source_artist_id)
    )
    for wa in res_wa.scalars().all():
        exists = await db.execute(
            select(WorkArtist).where(
                WorkArtist.work_id == wa.work_id,
                WorkArtist.artist_id == body.target_artist_id,
            )
        )
        if exists.scalar_one_or_none():
            await db.delete(wa)
        else:
            wa.artist_id = body.target_artist_id
    # Delete source artist
    await db.delete(source)
    await db.commit()
    logger.info(f"Merged artist {body.source_artist_id} into {body.target_artist_id}")
    return {
        "status": "merged",
        "source_artist_id": body.source_artist_id,
        "target_artist_id": body.target_artist_id,
    }


@router.post("/works/merge")
async def merge_works(
    body: MergeWorksRequest,
    db: AsyncSession = Depends(get_db),
):
    """Merge source work into target work (move recordings, then delete source).

    This endpoint is useful for fixing duplicate works that should have been
    merged by the fuzzy matching system but weren't (e.g., remixes/mixes that
    were incorrectly created as separate works instead of separate recordings).

    Args:
        body: Request containing source_work_id (to be deleted) and target_work_id (to be kept)
        db: Database session

    Returns:
        Status message with work IDs

    Raises:
        HTTPException: If works are the same, not found, or belong to different artists
    """
    if body.source_work_id == body.target_work_id:
        raise HTTPException(
            status_code=400, detail="Source and target work must differ"
        )

    # Load both works
    res = await db.execute(
        select(Work).where(Work.id.in_([body.source_work_id, body.target_work_id]))
    )
    works = {w.id: w for w in res.scalars().all()}
    source = works.get(body.source_work_id)
    target = works.get(body.target_work_id)

    if not source or not target:
        raise HTTPException(status_code=404, detail="Work not found")

    # Verify both works belong to the same artist
    if source.artist_id != target.artist_id:
        raise HTTPException(
            status_code=400,
            detail=f"Works belong to different artists (source: {source.artist_id}, target: {target.artist_id})"
        )

    # Move all recordings from source to target
    await db.execute(
        update(Recording)
        .where(Recording.work_id == body.source_work_id)
        .values(work_id=body.target_work_id)
    )

    # Expire the source work's recordings relationship to avoid SQLAlchemy issues
    db.expire(source, ['recordings'])

    # Delete source work
    await db.delete(source)
    await db.commit()

    logger.info(f"Merged work {body.source_work_id} into {body.target_work_id}")
    return {
        "status": "merged",
        "source_work_id": body.source_work_id,
        "target_work_id": body.target_work_id,
    }
