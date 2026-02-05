"""Intelligent matching engine for linking broadcast logs to library recordings.

This module implements a multi-strategy matching system that progressively
attempts different matching techniques from exact to fuzzy to semantic search.
The matcher is optimized for batch processing and uses confidence scoring
to determine match quality.

Matching Strategies (in order):
    1. Identity Bridge: Pre-verified permanent mappings
    2. Exact Match: Normalized exact string matching
    3. Variant Match: High fuzzy similarity (85% artist, 80% title)
    4. Vector Semantic: ChromaDB cosine similarity search
    5. Alias Match: Lower threshold for manual review (70%)

Typical usage example:
    matcher = Matcher(session)
    queries = [("Beatles", "Hey Jude"), ("Queen", "Bohemian Rhapsody")]
    results = await matcher.match_batch(queries)
    for (artist, title), (recording_id, reason) in results.items():
        print(f"{artist} - {title} matched to {recording_id}: {reason}")
"""

import difflib
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.core.config import settings
from airwave.core.models import (
    Artist,
    BroadcastLog,
    IdentityBridge,
    Recording,
    Work,
    DiscoveryQueue,
)
from sqlalchemy import delete, func
from airwave.core.normalization import Normalizer
from airwave.core.task_store import TaskStore
from airwave.core.vector_db import VectorDB


class Matcher:
    """Multi-strategy matching engine for broadcast log to recording linkage.

    This class implements an intelligent matching pipeline that attempts
    multiple strategies in order of confidence, from exact matches to
    semantic similarity searches. It's optimized for batch processing
    and includes diagnostic capabilities for troubleshooting.

    Matching thresholds are configured in settings (core/config.py):
        - MATCH_CONFIDENCE_HIGH_ARTIST: 0.85 (Artist similarity for variant match)
        - MATCH_CONFIDENCE_HIGH_TITLE: 0.80 (Title similarity for variant match)
        - MATCH_ALIAS_ARTIST_SCORE: 0.70 (Lower threshold for alias/manual review)
        - MATCH_VECTOR_STRONG_DIST: 0.15 (Max cosine distance for vector search)

    Attributes:
        session: Async SQLAlchemy database session.
        _vector_db: Lazy-loaded VectorDB instance for semantic search.
    """

    def __init__(self, session: AsyncSession):
        """Initializes the matcher with a database session.

        Args:
            session: Async SQLAlchemy session for database operations.
        """
        self.session = session

    async def match_batch(
        self, queries: List[Tuple[str, str]], explain: bool = False
    ) -> Dict[Tuple[str, str], Any]:
        """Efficiently matches a batch of raw artist/title pairs to recordings.

        This is the primary matching method that implements the full matching
        pipeline. It deduplicates queries, checks identity bridges, performs
        exact and fuzzy matching, and falls back to vector semantic search.

        The method is optimized for bulk operations with minimal database
        round-trips and efficient deduplication.

        Args:
            queries: List of (raw_artist, raw_title) tuples to match.
            explain: If True, returns detailed diagnostic information including
                candidate matches and scoring details. If False, returns only
                the best match for each query.

        Returns:
            Dictionary mapping (raw_artist, raw_title) to match results.

            If explain=False:
                {(artist, title): (recording_id, reason_string)}
                Example: {("Beatles", "Hey Jude"): (123, "Exact Match")}

            If explain=True:
                {(artist, title): {
                    "match": (recording_id, reason_string),
                    "candidates": [(id, score, reason), ...],
                    "note": "optional diagnostic note"
                }}

        Example:
            # Simple matching
            results = await matcher.match_batch([("Beatles", "Hey Jude")])
            recording_id, reason = results[("Beatles", "Hey Jude")]

            # Diagnostic matching
            results = await matcher.match_batch(
                [("Beatles", "Hey Jude")],
                explain=True
            )
            match_info = results[("Beatles", "Hey Jude")]
            print(f"Best match: {match_info['match']}")
            print(f"Candidates: {match_info['candidates']}")
        """
        print(f"DEBUG: match_batch called with {queries}")
        results = {}

        # 0. Deduplicate
        unique_queries = list(set(queries))
        if not unique_queries:
            return {}

        # Pre-calculate signatures and normalized forms
        sig_map = {}
        norm_map = {}

        for qa, qt in unique_queries:
            sig = Normalizer.generate_signature(qa, qt)
            if sig not in sig_map:
                sig_map[sig] = []
            sig_map[sig].append((qa, qt))

            ca, ct = Normalizer.clean_artist(qa), Normalizer.clean(qt)
            if (ca, ct) not in norm_map:
                norm_map[(ca, ct)] = []
            norm_map[(ca, ct)].append((qa, qt))

        signatures = list(sig_map.keys())

        # 1. Bulk Identity Bridge Lookup
        # Note: IdentityBridge now links to recording_id

        # 1. Bulk Identity Bridge Lookup
        # Note: IdentityBridge now links to recording_id

        stmt = select(IdentityBridge).where(
            IdentityBridge.log_signature.in_(signatures)
        )
        res = await self.session.execute(stmt)
        bridges = res.scalars().all()

        found_signatures = set()

        # If explaining, we still want to know if a bridge exists
        bridge_matches = {}

        for b in bridges:
            found_signatures.add(b.log_signature)
            for original in sig_map[b.log_signature]:
                match_res = (b.recording_id, "Identity Bridge (Exact Match)")
                if explain:
                    bridge_matches[original] = match_res
                else:
                    results[original] = match_res

        # 2. Identify residuals
        residuals = []
        for sig in signatures:
            if sig not in found_signatures:
                for original in sig_map[sig]:
                    residuals.append(original)

        if not residuals:
            return results

        residual_norms = set()
        for ra, rt in residuals:
            residual_norms.add((Normalizer.clean_artist(ra), Normalizer.clean(rt)))

        residual_norms_list = list(residual_norms)

        # 2. Exact Match Step (SQL Lookup)
        # Optimized to Find Exact Matches when Vector DB might be empty/missed
        if residual_norms_list:
            # Batch in chunks of 500 for SQL limit safety
            exact_matches_found = {}
            for i in range(0, len(residual_norms_list), 500):
                chunk = residual_norms_list[i : i + 500]
                print(f"DEBUG: Matcher looking for chunks: {chunk}")
                stmt = (
                    select(Recording)
                    .join(Work)
                    .join(Artist)
                    .where(
                        tuple_(Artist.name, Recording.title).in_(chunk)
                    )
                    .options(
                         selectinload(Recording.work).selectinload(Work.artist),
                         selectinload(Recording.work).selectinload(Work.artists),
                    )
                )
                res = await self.session.execute(stmt)
                found_recordings = res.scalars().all()
                print(f"DEBUG: Matcher found: {found_recordings}")
                
                for rec in found_recordings:
                    # Map back to clean keys
                    # Note: We assume normalization is stable
                    # Artist name on DB is already clean. Recording title is virtual title (clean).
                    # But we need to handle case where multiple artists exist?
                    # Using Primary Artist for now as per key.
                    
                    # We need to construct the key (artist_name, title) exactly as in chunk
                    # Artist.name is unique.
                    if rec.work and rec.work.artist:
                        key = (rec.work.artist.name, rec.title)
                        exact_matches_found[key] = rec

            # Assign Exact Matches
            remaining_residuals = []
            for clean_pair in residual_norms_list:
                rec = exact_matches_found.get(clean_pair)
                if rec:
                     # Find all original queries that map to this clean pair
                    originals = norm_map.get(clean_pair, [])
                    for raw_q in originals:
                        match_res = (rec.id, "Exact DB Match")
                        if explain:
                            results[raw_q] = {
                                "match": match_res,
                                "candidates": [],
                                "note": "Exact SQL Match"
                            }
                        else:
                            results[raw_q] = match_res
                else:
                    remaining_residuals.append(clean_pair)
            
            # Update residual list for Vector Search
            residual_norms_list = remaining_residuals

        if not residual_norms_list:
             return results

        if not hasattr(self, "_vector_db"):
            self._vector_db = VectorDB()

        # 3. Batch Search
        # Returns List of Lists of (recording_id, distance)
        limit = 10 if explain else 10
        batch_search_results = self._vector_db.search_batch(
            residual_norms_list, limit=limit
        )

        # 4. Fetch All Candidates Efficiently (With Joins)
        all_candidate_ids = set()
        for matches in batch_search_results:
            for tid, _ in matches:
                all_candidate_ids.add(tid)

        track_objects = {}
        if all_candidate_ids:
            # We are fetching RECORDINGS
            # Need to join Work and Artist to get the Artist Name
            stmt = (
                select(Recording)
                .options(
                    selectinload(Recording.work).selectinload(Work.artist),
                    selectinload(Recording.work).selectinload(Work.artists),
                )
                .where(Recording.id.in_(list(all_candidate_ids)))
            )
            res = await self.session.execute(stmt)
            track_objects = {t.id: t for t in res.scalars().all()}

        # 5. Process Matches
        for i, (clean_a, clean_t) in enumerate(residual_norms_list):
            top_matches = batch_search_results[i]

            best_match = (None, "No Match Found")
            candidates_debug = []

            # Helper to find which original raw inputs map to this cleaned pair
            originals = norm_map.get((clean_a, clean_t), [])

            # First pass: Scoring Candidates
            for tid, dist in top_matches:
                recording = track_objects.get(tid)
                if not recording:
                    continue
                # Handle possible missing relations (though unlikely with strict integrity)
                rec_title = recording.title

                # Multi-Artist Scoring: Check all associated artists
                best_artist_sim = 0.0
                associated_artists = (
                    recording.work.artists if recording.work else []
                )
                # Fallback to primary artist if relationship not loaded or empty
                if (
                    not associated_artists
                    and recording.work
                    and recording.work.artist
                ):
                    associated_artists = [recording.work.artist]

                for artist_obj in associated_artists:
                    clean_track_artist = Normalizer.clean_artist(
                        artist_obj.name
                    )
                    sim = difflib.SequenceMatcher(
                        None, clean_track_artist, clean_a
                    ).ratio()
                    if sim > best_artist_sim:
                        best_artist_sim = sim

                artist_sim = best_artist_sim
                clean_track_title = Normalizer.clean(rec_title)
                title_sim = difflib.SequenceMatcher(
                    None, clean_track_title, clean_t
                ).ratio()

                candidate_info = {
                    "track": recording,  # Kept name 'track' for compatibility with debug loop below
                    "artist_sim": artist_sim,
                    "title_sim": title_sim,
                    "vector_dist": dist,
                    "score_desc": f"A:{int(artist_sim*100)} T:{int(title_sim*100)} V:{1-dist:.2f}",
                    "match_type": "None",
                }

                # Check Match Logic (Iterative)
                is_exact = (
                    clean_track_artist == clean_a
                    and clean_track_title == clean_t
                )

                if is_exact:
                    candidate_info["match_type"] = "Exact"
                    if best_match[0] is None:
                        best_match = (tid, "Exact Text Match (Cleaned)")

                elif (
                    artist_sim > settings.MATCH_CONFIDENCE_HIGH_ARTIST
                    and title_sim > settings.MATCH_CONFIDENCE_HIGH_TITLE
                ):
                    candidate_info["match_type"] = "High Confidence"
                    if best_match[0] is None:
                        best_match = (
                            tid,
                            f"High Confidence Match (Artist: {int(artist_sim*100)}%, Title: {int(title_sim*100)}%, Vector: {1-dist:.2f})",
                        )

                elif (
                    dist < settings.MATCH_VECTOR_STRONG_DIST
                    and title_sim >= settings.MATCH_VECTOR_TITLE_GUARD
                ):
                    candidate_info["match_type"] = "Vector Strong"
                    if best_match[0] is None:
                        best_match = (
                            tid,
                            f"Vector Similarity (Very High: {1-dist:.2f})",
                        )

                elif (
                    title_sim > settings.MATCH_TITLE_VECTOR_TITLE
                    and dist < settings.MATCH_TITLE_VECTOR_DIST
                ):
                    candidate_info["match_type"] = "Title+Vector"
                    if best_match[0] is None:
                        best_match = (
                            tid,
                            f"Title Match + Vector (Confidence: {1-dist:.2f})",
                        )

                candidates_debug.append(candidate_info)

            # Use 'best_match' found in loop (first priority win)

            for raw_q in originals:
                if explain:
                    # Enrich candidates with serializable track info
                    serializable_candidates = []
                    for c in candidates_debug:
                        t = c["track"]
                        # Get Artist Name again safely
                        aname = (
                            t.work.artist.name
                            if t.work and t.work.artist
                            else "Unknown"
                        )
                        serializable_candidates.append(
                            {
                                "recording_id": t.id,
                                "artist": aname,
                                "title": t.title,
                                "artist_sim": c["artist_sim"],
                                "title_sim": c["title_sim"],
                                "vector_dist": c["vector_dist"],
                                "match_type": c["match_type"],
                            }
                        )

                    results[raw_q] = {
                        "match": best_match,
                        "candidates": serializable_candidates,
                    }
                else:
                    results[raw_q] = best_match

        # Merge Bridge Matches if explaining
        if explain:
            for original, res in bridge_matches.items():
                results[original] = {
                    "match": res,
                    "candidates": [],  # No candidates for bridge matches usually
                    "note": "Identity Bridge",
                }

        return results

    async def find_match(
        self, raw_artist: str, raw_title: str
    ) -> tuple[Optional[int], str]:
        """Attempt to match a log entry to a local track."""
        res = await self.match_batch([(raw_artist, raw_title)])
        return res.get((raw_artist, raw_title), (None, "No Match Found"))

    async def run_discovery(self, task_id: Optional[str] = None) -> int:
        """Rebuilds the DiscoveryQueue from unmatched logs.
        
        Instead of creating 'Ghost Recordings', this method aggregates unmatched
        broadcast logs into the DiscoveryQueue table. It then attempts to find
        suggestions by matching against the existing library.
        """
        logger.info("Starting Run Discovery (Queue Rebuild)...")

        # 1. Clear existing Queue to ensure fresh state
        await self.session.execute(delete(DiscoveryQueue))
        
        # 2. Fetch Unmatched Logs (Aggregated by Raw Text)
        # We group by raw text first to let SQL do the heavy lifting of counting identical strings
        stmt = (
            select(
                BroadcastLog.raw_artist, 
                BroadcastLog.raw_title, 
                func.count(BroadcastLog.id)
            )
            .where(BroadcastLog.recording_id.is_(None))
            .group_by(BroadcastLog.raw_artist, BroadcastLog.raw_title)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        
        if not rows:
            logger.info("No unmatched logs found.")
            if task_id:
                TaskStore.update_progress(task_id, 100, "No unmatched logs found.")
            return 0

        # 3. Group by Normalized Signature in Python
        # Different raw strings might normalize to the same signature (Case, minor spacing).
        # We aggregate them here.
        sig_map = {}  # signature -> {signature, raw_artist, raw_title, count}
        
        for r_artist, r_title, count in rows:
            if not r_artist or not r_title: 
                continue
                
            sig = Normalizer.generate_signature(r_artist, r_title)
            
            if sig not in sig_map:
                sig_map[sig] = {
                    "signature": sig,
                    "raw_artist": r_artist, # Keep the first one encountered as display
                    "raw_title": r_title,
                    "count": 0
                }
            
            sig_map[sig]["count"] += count
            
        queue_items = list(sig_map.values())
        total_items = len(queue_items)
        logger.info(f"Aggregated into {total_items} unique signatures.")
        
        if task_id:
             TaskStore.update_total(task_id, total_items, f"Processing {total_items} discovery items...")

        # 4. Create Queue Objects
        dq_objects = [DiscoveryQueue(**item) for item in queue_items]
        self.session.add_all(dq_objects)
        await self.session.flush() # Flush to ensure they are tracked, though we don't need IDs yet (PK is signature)
        
        # 5. Run Automatch for Suggestions
        # Process in batches to efficiently find suggestions without overloading
        BATCH_SIZE = 500
        processed = 0
        
        # Map for quick update
        obj_map = {obj.signature: obj for obj in dq_objects}
        
        for i in range(0, total_items, BATCH_SIZE):
            batch_objs = dq_objects[i : i + BATCH_SIZE]
            batch_queries = [(obj.raw_artist, obj.raw_title) for obj in batch_objs]
            
            # Use existing efficient match_batch
            matches = await self.match_batch(batch_queries)
            
            for (qa, qt), (rec_id, _) in matches.items():
                if rec_id:
                    sig = Normalizer.generate_signature(qa, qt)
                    if sig in obj_map:
                        obj_map[sig].suggested_recording_id = rec_id
            
            processed += len(batch_objs)
            if task_id and i % 1000 == 0:
                 TaskStore.update_progress(
                    task_id, 
                    processed, 
                    f"Analyzed {processed}/{total_items} items..."
                )

        await self.session.commit()
        logger.success(f"Discovery Queue Rebuilt. {total_items} items active.")
        return total_items

    async def link_orphaned_logs(self) -> int:
        """Links logs that have a NULL recording_id to a recording via IdentityBridge."""
        stmt = select(BroadcastLog).where(BroadcastLog.recording_id.is_(None))
        result = await self.session.stream(stmt)

        updated_count = 0

        async for row in result:
            log = row.BroadcastLog
            signature = Normalizer.generate_signature(
                log.raw_artist, log.raw_title
            )

            stmt = select(IdentityBridge).where(
                IdentityBridge.log_signature == signature
            )
            res = await self.session.execute(stmt)
            bridge = res.scalar_one_or_none()

            if bridge:
                log.recording_id = bridge.recording_id
                log.match_reason = "Auto-Promoted Identity"
                updated_count += 1

        await self.session.commit()
        return updated_count
