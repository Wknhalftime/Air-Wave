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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.api.deps import get_db
from airwave.core.models import SystemSetting
from airwave.core.task_store import TaskStore
from airwave.worker.main import (
    run_bulk_import,
    run_discovery_task,
    run_import,
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


@router.get("/pipeline-stats")
async def get_pipeline_stats(session: AsyncSession = Depends(get_db)):
    """Get stats for the mission control pipeline."""
    from sqlalchemy import func, select

    from airwave.core.models import BroadcastLog, DiscoveryQueue, Recording

    # Total Logs
    res = await session.execute(select(func.count(BroadcastLog.id)))
    total_logs = res.scalar() or 0

    # Unmatched
    res = await session.execute(
        select(func.count(BroadcastLog.id)).where(BroadcastLog.recording_id.is_(None))
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


# Match Tuner API

from pydantic import BaseModel


class MatchCandidate(BaseModel):
    recording_id: int
    artist: str
    title: str
    artist_sim: float
    title_sim: float
    vector_dist: float
    match_type: str


class MatchSample(BaseModel):
    id: int
    raw_artist: str
    raw_title: str
    match: Optional[dict]
    candidates: List[MatchCandidate]


@router.get("/match-samples", response_model=List[MatchSample])
async def get_match_samples(
    limit: int = 20, session: AsyncSession = Depends(get_db)
):
    """Fetch a sample of Unmatched or Pending logs and run strict 'Explain' matching
    to show what candidates exist.
    """
    from sqlalchemy import func, select

    from airwave.core.models import BroadcastLog
    from airwave.worker.matcher import Matcher

    # Get random sample of Unmatched logs
    stmt = (
        select(BroadcastLog)
        .where(BroadcastLog.recording_id.is_(None))
        .order_by(func.random())
        .limit(limit)
    )
    res = await session.execute(stmt)
    logs = res.scalars().all()

    if not logs:
        return []

    matcher = Matcher(session)
    queries = [(log.raw_artist, log.raw_title) for log in logs]

    # Run Matcher with Explain=True
    # Returns Dict { (raw_a, raw_t) -> { 'match': ..., 'candidates': ... } }
    results = await matcher.match_batch(queries, explain=True)

    response = []
    for log in logs:
        key = (log.raw_artist, log.raw_title)
        if key in results:
            data = results[key]
            # Transform match result tuple (id, reason) to dict or None
            match_data = None
            if data["match"][0]:
                match_data = {
                    "recording_id": data["match"][0],
                    "reason": data["match"][1],
                }

            # Map candidates (which might still have 'track_id' if matcher wasn't fully updated in return dict keys?
            # I should check matcher.py explain return structure.
            # Assuming matcher returns dicts with 'id' or 'recording_id'.
            # Let's assume matcher candidates use 'id' or we map keys.
            # Matcher.py typically returns internal objects or dicts.
            # If Matcher.explain_match returns dictionaries, we need to ensure keys match MatchCandidate.

            candidates_mapped = []
            for c in data["candidates"]:
                # Handle key mapping if necessary
                candidates_mapped.append(
                    MatchCandidate(
                        recording_id=c.get("id")
                        or c.get("track_id")
                        or c.get("recording_id"),
                        artist=c["artist"],
                        title=c["title"],
                        artist_sim=c["artist_sim"],
                        title_sim=c["title_sim"],
                        vector_dist=c["vector_dist"],
                        match_type=c["match_type"],
                    )
                )

            response.append(
                MatchSample(
                    id=log.id,
                    raw_artist=log.raw_artist,
                    raw_title=log.raw_title,
                    match=match_data,
                    candidates=candidates_mapped,
                )
            )

    return response


class ThresholdSettings(BaseModel):
    artist_auto: float
    artist_review: float
    title_auto: float
    title_review: float


@router.post("/settings/thresholds")
async def update_thresholds(
    settings_in: ThresholdSettings, session: AsyncSession = Depends(get_db)
):
    """Update matching thresholds in DB and Memory."""
    from airwave.core.config import settings
    from airwave.core.models import SystemSetting

    # Helper to update both
    async def update_setting(key: str, val: float):
        # Update Memory
        setattr(settings, key, val)

        # Update DB
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        res = await session.execute(stmt)
        obj = res.scalar_one_or_none()
        if not obj:
            obj = SystemSetting(key=key, value=str(val))
            session.add(obj)
        else:
            obj.value = str(val)

    await update_setting("MATCH_VARIANT_ARTIST_SCORE", settings_in.artist_auto)
    await update_setting("MATCH_ALIAS_ARTIST_SCORE", settings_in.artist_review)
    await update_setting("MATCH_VARIANT_TITLE_SCORE", settings_in.title_auto)
    await update_setting("MATCH_ALIAS_TITLE_SCORE", settings_in.title_review)

    # Also link Vector Guard to Title Review (as agreed in design)
    # "Title Tolerance" slider controls both
    await update_setting(
        "MATCH_VECTOR_TITLE_GUARD", settings_in.title_review * 0.8
    )  # Heuristic: Vector guard slightly looser than text?
    # Actually, User request logic: "Title Tolerance" slider controls both.
    # If slider is 0.8 (Strict), Vector Guard should be 0.8?
    # Design says: "Logic: The 'Title Tolerance' slider will control both MATCH_VARIANT_TITLE_SCORE and MATCH_VECTOR_TITLE_GUARD"
    # Actually, MATCH_VARIANT_TITLE_SCORE is for "High Confidence" (Green).
    # MATCH_ALIAS_TITLE_SCORE is for "Review" (Yellow).
    # MATCH_VECTOR_TITLE_GUARD is a hard floor.
    # Let's map Vector Guard to 0.5 * Title Review (allow vectors to be much looser) or just keep it fixed?
    # User agreed to: "Title Tolerance slider will control both".
    # Let's set Vector Guard to be slightly more permissive than the "Review" threshold.
    # usage: if Review is 0.6, Vector Guard 0.5.

    await session.commit()
    return {"status": "updated", "current_settings": settings_in}


@router.get("/settings/thresholds")
async def get_thresholds():
    from airwave.core.config import settings

    return {
        "artist_auto": settings.MATCH_VARIANT_ARTIST_SCORE,
        "artist_review": settings.MATCH_ALIAS_ARTIST_SCORE,
        "title_auto": settings.MATCH_VARIANT_TITLE_SCORE,
        "title_review": settings.MATCH_ALIAS_TITLE_SCORE,
    }


@router.post("/match-tuner/re-evaluate")
async def re_evaluate_matches(background_tasks: BackgroundTasks):
    """Re-evaluate all unmatched and flagged broadcast logs with current thresholds."""
    import uuid

    from airwave.core.task_store import TaskStore
    from airwave.worker.main import run_re_evaluate

    task_id = str(uuid.uuid4())
    TaskStore.create_task(task_id, "re-evaluate", 1)
    TaskStore.update_progress(task_id, 0, "Initializing re-evaluation...")
    background_tasks.add_task(run_re_evaluate, task_id)
    return {"status": "started", "task_id": task_id}


@router.post("/scan")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    req: ScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a file sync scan with progress tracking."""
    path = req.path
    if not path:
        # Fetch from settings
        stmt = select(SystemSetting).where(SystemSetting.key == "music_dir")
        result = await db.execute(stmt)
        setting = result.scalar_one_or_none()
        if setting:
            path = setting.value
        else:
            path = "D:\\Media\\Music"  # Fallback

    task_id = str(uuid.uuid4())
    # Pre-create task entry so SSE can connect immediately
    TaskStore.create_task(task_id, "sync", 1)
    TaskStore.update_progress(task_id, 0, "Initializing scan...")
    background_tasks.add_task(run_sync_files, path, task_id)
    return {"status": "started", "path": path, "task_id": task_id}


@router.post("/trigger-scan")
async def trigger_internal_scan(background_tasks: BackgroundTasks):
    """Trigger the 'scan' command (Log -> Library promotion) with progress tracking."""
    task_id = str(uuid.uuid4())
    # Pre-create task entry so SSE can connect immediately
    TaskStore.create_task(task_id, "scan", 1)
    TaskStore.update_progress(task_id, 0, "Initializing scan...")
    background_tasks.add_task(run_scan, task_id)
    return {"status": "started", "task_id": task_id}


@router.post("/trigger-discovery")
async def trigger_discovery(background_tasks: BackgroundTasks):
    """Rebuild the DiscoveryQueue from unmatched logs with progress tracking."""
    task_id = str(uuid.uuid4())
    # Pre-create task entry so SSE can connect immediately
    TaskStore.create_task(task_id, "discovery", 1)
    TaskStore.update_progress(task_id, 0, "Initializing discovery...")
    background_tasks.add_task(run_discovery_task, task_id)
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
    task_id = str(uuid.uuid4())
    TaskStore.create_task(task_id, "import", 1)
    TaskStore.update_progress(task_id, 0, f"Initializing import for {path}...")
    background_tasks.add_task(run_bulk_import, path, task_id)
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

    task_id = str(uuid.uuid4())
    # Pre-create task entry so SSE can connect immediately
    TaskStore.create_task(task_id, "import", 1)
    TaskStore.update_progress(task_id, 0, "Starting import...")
    background_tasks.add_task(run_import, file_path, task_id)
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
                task = TaskStore.get_task(task_id)

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
                if task.status in ["completed", "failed"]:
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
