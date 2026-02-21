"""Match Tuner API endpoints for threshold tuning and sample analysis."""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.api.deps import get_db
from airwave.api.schemas import (
    MatchCandidate,
    MatchImpactResponse,
    MatchSample,
    ThresholdSettings,
)
from airwave.core.config import settings
from airwave.core.models import BroadcastLog, SystemSetting
from airwave.core.task_store import create_task, update_progress
from airwave.services.match_quality import analyze_match_quality, detect_edge_case
from airwave.worker.main import run_re_evaluate
from airwave.worker.matcher import Matcher

router = APIRouter(tags=["Match Tuner"])


@router.get("/match-samples", response_model=List[MatchSample])
async def get_match_samples(
    limit: int = 10,
    artist_auto: Optional[float] = None,
    artist_review: Optional[float] = None,
    title_auto: Optional[float] = None,
    title_review: Optional[float] = None,
    stratified: bool = False,
    session: AsyncSession = Depends(get_db),
):
    """Fetch a sample of Unmatched logs and run strict 'Explain' matching.

    Performance Note: This endpoint runs expensive vector searches with explain=True.
    Default limit reduced to 10 to keep response time under 2 seconds.
    """
    thresholds = {
        "artist_auto": artist_auto or settings.MATCH_VARIANT_ARTIST_SCORE,
        "artist_review": artist_review or settings.MATCH_ALIAS_ARTIST_SCORE,
        "title_auto": title_auto or settings.MATCH_VARIANT_TITLE_SCORE,
        "title_review": title_review or settings.MATCH_ALIAS_TITLE_SCORE,
    }

    sample_size = 1000 if stratified else limit
    stmt = (
        select(BroadcastLog)
        .where(BroadcastLog.work_id.is_(None))
        .order_by(func.random())
        .limit(sample_size)
    )
    res = await session.execute(stmt)
    logs = res.scalars().all()

    if not logs:
        return []

    matcher = Matcher(session)
    queries = [(log.raw_artist, log.raw_title) for log in logs]
    results = await matcher.match_batch(queries, explain=True)

    all_samples = []
    for log in logs:
        key = (log.raw_artist, log.raw_title)
        if key in results:
            data = results[key]
            match_id = data["match"][0]
            reason = data["match"][1] if data["match"][0] else ""

            match_data = None
            if match_id:
                match_data = {"recording_id": match_id, "reason": reason}

            category = None
            action = None
            artist_sim = None
            title_sim = None

            if match_id and data["candidates"]:
                best = data["candidates"][0]
                artist_sim = best["artist_sim"]
                title_sim = best["title_sim"]

                if "Identity Bridge" in reason:
                    category = "identity_bridge"
                    action = "auto_link"
                elif (
                    artist_sim >= thresholds["artist_auto"]
                    and title_sim >= thresholds["title_auto"]
                ):
                    category = "auto_link"
                    action = "auto_link"
                elif (
                    artist_sim >= thresholds["artist_review"]
                    and title_sim >= thresholds["title_review"]
                ):
                    category = "review"
                    action = "suggest"
                else:
                    category = "reject"
                    action = "ignore"

            candidates_mapped = []
            for c in data["candidates"][:5]:
                quality_warnings = analyze_match_quality(
                    log.raw_artist, log.raw_title, c["artist"], c["title"]
                )
                edge_case = detect_edge_case(
                    c["artist_sim"], c["title_sim"], thresholds
                )
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
                        quality_warnings=quality_warnings,
                        edge_case=edge_case,
                    )
                )

            sample = MatchSample(
                id=log.id,
                raw_artist=log.raw_artist,
                raw_title=log.raw_title,
                match=match_data,
                candidates=candidates_mapped,
                category=category,
                action=action,
            )
            all_samples.append(
                {
                    "sample": sample,
                    "artist_sim": artist_sim,
                    "title_sim": title_sim,
                    "category": category,
                }
            )

    if stratified:
        near_auto = []
        in_review = []
        near_review = []
        identity_bridge = []
        for item in all_samples:
            if item["artist_sim"] is None or item["title_sim"] is None:
                continue
            artist_sim = item["artist_sim"]
            title_sim = item["title_sim"]
            if item["category"] == "identity_bridge":
                identity_bridge.append(item)
            elif (
                artist_sim >= thresholds["artist_auto"]
                and title_sim >= thresholds["title_auto"]
            ):
                near_auto.append(item)
            elif (
                artist_sim >= thresholds["artist_review"]
                and title_sim >= thresholds["title_review"]
            ):
                in_review.append(item)
            else:
                near_review.append(item)

        near_auto_sorted = sorted(
            near_auto, key=lambda x: min(x["artist_sim"], x["title_sim"])
        )[:15]
        in_review_sorted = sorted(
            in_review,
            key=lambda x: abs(
                min(x["artist_sim"], x["title_sim"])
                - (thresholds["artist_auto"] + thresholds["artist_review"]) / 2
            ),
        )[:15]
        near_review_sorted = sorted(
            near_review,
            key=lambda x: abs(
                min(x["artist_sim"], x["title_sim"])
                - thresholds["artist_review"]
            ),
            reverse=True,
        )[:15]
        identity_bridge_sorted = identity_bridge[:10]

        response = [
            item["sample"]
            for item in identity_bridge_sorted
            + near_auto_sorted
            + in_review_sorted
            + near_review_sorted
        ]
    else:
        response = [item["sample"] for item in all_samples[:limit]]

    return response


@router.get("/match-impact", response_model=MatchImpactResponse)
async def get_match_impact(
    artist_auto: float,
    artist_review: float,
    title_auto: float,
    title_review: float,
    sample_size: int = 1000,
    session: AsyncSession = Depends(get_db),
):
    """Analyze the impact of threshold settings on unmatched logs."""
    if not (
        0 <= artist_auto <= 1
        and 0 <= artist_review <= 1
        and 0 <= title_auto <= 1
        and 0 <= title_review <= 1
    ):
        raise HTTPException(
            status_code=400, detail="Thresholds must be between 0 and 1"
        )

    if artist_review > artist_auto or title_review > title_auto:
        raise HTTPException(
            status_code=400,
            detail="Review thresholds must be lower than auto-accept thresholds",
        )

    sample_size = min(sample_size, 5000)

    count_stmt = select(func.count()).select_from(BroadcastLog).where(
        BroadcastLog.work_id.is_(None)
    )
    total_result = await session.execute(count_stmt)
    total_unmatched = total_result.scalar() or 0

    if total_unmatched == 0:
        return MatchImpactResponse(
            total_unmatched=0,
            sample_size=0,
            auto_link_count=0,
            auto_link_percentage=0.0,
            review_count=0,
            review_percentage=0.0,
            reject_count=0,
            reject_percentage=0.0,
            identity_bridge_count=0,
            identity_bridge_percentage=0.0,
            edge_cases={"within_5pct_of_auto": 0, "within_5pct_of_review": 0},
            thresholds_used={
                "artist_auto": artist_auto,
                "artist_review": artist_review,
                "title_auto": title_auto,
                "title_review": title_review,
            },
        )

    actual_sample_size = min(sample_size, total_unmatched)
    stmt = (
        select(BroadcastLog)
        .where(BroadcastLog.work_id.is_(None))
        .order_by(func.random())
        .limit(actual_sample_size)
    )
    res = await session.execute(stmt)
    logs = res.scalars().all()

    matcher = Matcher(session)
    queries = [(log.raw_artist, log.raw_title) for log in logs]
    results = await matcher.match_batch(queries, explain=True)

    auto_link_count = 0
    review_count = 0
    reject_count = 0
    identity_bridge_count = 0
    edge_cases_auto = 0
    edge_cases_review = 0

    for log in logs:
        key = (log.raw_artist, log.raw_title)
        if key not in results:
            reject_count += 1
            continue

        data = results[key]
        match_id = data["match"][0]
        reason = data["match"][1] if data["match"][0] else ""

        if not match_id or not data["candidates"]:
            reject_count += 1
            continue

        best = data["candidates"][0]
        artist_sim = best["artist_sim"]
        title_sim = best["title_sim"]
        match_type = best["match_type"]

        if "Identity Bridge" in reason:
            identity_bridge_count += 1
            auto_link_count += 1
        elif match_type == "Exact":
            review_count += 1
        elif match_type == "High Confidence":
            if artist_sim >= artist_auto and title_sim >= title_auto:
                auto_link_count += 1
                if artist_sim < artist_auto + 0.05 or title_sim < title_auto + 0.05:
                    edge_cases_auto += 1
            else:
                review_count += 1
        elif match_type == "Review Confidence":
            review_count += 1
            if artist_sim < artist_review + 0.05 or title_sim < title_review + 0.05:
                edge_cases_review += 1
        elif "Vector" in match_type:
            if artist_sim >= artist_review and title_sim >= title_review:
                review_count += 1
            else:
                reject_count += 1
        else:
            reject_count += 1

    auto_link_pct = (
        (auto_link_count / actual_sample_size * 100) if actual_sample_size > 0 else 0
    )
    review_pct = (
        (review_count / actual_sample_size * 100) if actual_sample_size > 0 else 0
    )
    reject_pct = (
        (reject_count / actual_sample_size * 100) if actual_sample_size > 0 else 0
    )
    identity_bridge_pct = (
        (identity_bridge_count / actual_sample_size * 100)
        if actual_sample_size > 0
        else 0
    )

    return MatchImpactResponse(
        total_unmatched=total_unmatched,
        sample_size=actual_sample_size,
        auto_link_count=auto_link_count,
        auto_link_percentage=round(auto_link_pct, 1),
        review_count=review_count,
        review_percentage=round(review_pct, 1),
        reject_count=reject_count,
        reject_percentage=round(reject_pct, 1),
        identity_bridge_count=identity_bridge_count,
        identity_bridge_percentage=round(identity_bridge_pct, 1),
        edge_cases={
            "within_5pct_of_auto": edge_cases_auto,
            "within_5pct_of_review": edge_cases_review,
        },
        thresholds_used={
            "artist_auto": artist_auto,
            "artist_review": artist_review,
            "title_auto": title_auto,
            "title_review": title_review,
        },
    )


@router.post("/settings/thresholds")
async def update_thresholds(
    settings_in: ThresholdSettings, session: AsyncSession = Depends(get_db)
):
    """Update matching thresholds in DB and Memory."""

    async def update_setting(key: str, val: float):
        setattr(settings, key, val)
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        res = await session.execute(stmt)
        obj = res.scalar_one_or_none()
        if not obj:
            obj = SystemSetting(key=key, value=str(val))
            session.add(obj)
        else:
            obj.value = str(val)

    mapping = {
        "MATCH_VARIANT_ARTIST_SCORE": settings_in.artist_auto,
        "MATCH_ALIAS_ARTIST_SCORE": settings_in.artist_review,
        "MATCH_VARIANT_TITLE_SCORE": settings_in.title_auto,
        "MATCH_ALIAS_TITLE_SCORE": settings_in.title_review,
    }
    for key, val in mapping.items():
        await update_setting(key, val)

    await update_setting(
        "MATCH_VECTOR_TITLE_GUARD", settings_in.title_review * 0.8
    )

    await session.commit()
    return {"status": "updated", "current_settings": settings_in}


@router.get("/settings/thresholds")
async def get_thresholds():
    """Get current matching thresholds."""
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

    task_id = str(uuid.uuid4())
    create_task(task_id, "re-evaluate", 1)
    update_progress(task_id, 0, "Initializing re-evaluation...")
    background_tasks.add_task(run_re_evaluate, task_id)
    return {"status": "started", "task_id": task_id}
