"""CSV import engine for broadcast log ingestion.

This module provides high-performance CSV import functionality using DuckDB
for ultra-fast parsing (100k+ rows/second). It handles broadcast log files
from radio stations, performs automatic station detection, and integrates
with the matching engine for identity resolution.

The importer supports:
- DuckDB-accelerated CSV parsing with automatic fallback
- Chunked processing to avoid SQLite variable limits
- Flexible date parsing for various log formats
- Station caching for performance
- Identity resolution and matching integration

Typical usage example:
    importer = CSVImporter(session)
    for chunk in importer.read_csv_stream("logs.csv", chunk_size=1000):
        count = await importer.process_batch(batch_id, chunk)
        print(f"Imported {count} rows")
"""

from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

import duckdb
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.core.models import BroadcastLog, Recording, Station
from airwave.core.utils import parse_flexible_date
from airwave.worker.identity_resolver import IdentityResolver
from airwave.worker.matcher import Matcher


class CSVImporter:
    """High-performance CSV importer for broadcast logs using DuckDB.

    This class handles the ingestion of radio station broadcast logs from
    CSV files. It uses DuckDB for extremely fast CSV parsing (100x faster
    than pandas/csv module) and processes data in chunks to avoid SQLite
    variable limits.

    The importer automatically:
    - Detects and caches station records
    - Parses flexible date formats
    - Resolves artist identities
    - Matches logs to library recordings
    - Tracks import batches

    Attributes:
        session: Async SQLAlchemy database session.
        matcher: Matcher instance for log-to-recording matching.
        identity_resolver: IdentityResolver for artist alias resolution.
        station_cache: In-memory cache of station records by callsign.
    """

    def __init__(self, session: AsyncSession):
        """Initializes the CSV importer with database session.

        Args:
            session: Async SQLAlchemy session for database operations.
        """
        self.session = session
        self.matcher = Matcher(session)
        self.identity_resolver = IdentityResolver(session)
        self.station_cache = {}

    def read_csv_stream(
        self, file_path: str, chunk_size: int = 50000
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """Reads CSV file using DuckDB for ultra-fast parsing.

        This method uses DuckDB's optimized CSV reader which is significantly
        faster than pandas or the standard csv module. It automatically falls
        back to standard CSV reading if DuckDB fails.

        The method yields chunks of dictionaries to maintain compatibility
        with existing batch processing code while leveraging DuckDB's speed.

        Args:
            file_path: Path to the CSV file to import.
            chunk_size: Number of rows per chunk. Defaults to 50000.
                Larger chunks are faster but use more memory.

        Yields:
            Lists of dictionaries, where each dictionary represents one row
            with column names as keys. None values are converted to empty
            strings for consistency.

        Example:
            for chunk in importer.read_csv_stream("logs.csv", chunk_size=1000):
                print(f"Processing {len(chunk)} rows")
                for row in chunk:
                    print(f"{row['artist']} - {row['title']}")

        Note:
            DuckDB requires forward slashes in paths on Windows. The method
            automatically handles path normalization.
        """
        try:
            # DuckDB reads the CSV incredibly fast (milliseconds for 100k rows)
            # We explicitly define types to avoid ambiguity
            # Auto-detect is usually good, but we can hint if needed
            logger.info(f"DuckDB: Reading {file_path}...")

            # Using duckdb to query safely
            # We select * from the file
            # We can use offset/limit for chunking if file is massive (GBs),
            # but for 100k-1M rows, loading into memory is fine.

            # Optimization: If the file is HUGE, we should use OFFSET/LIMIT.
            # But DuckDB's result conversion to Python objects might be the bottleneck.
            # For compatibility, we'll yield one large chunk or split it.

            # Normalize path for Windows (DuckDB SQL needs forward slashes or escaped backslashes)
            safe_path = file_path.replace("\\", "/")

            con = duckdb.connect(database=":memory:")

            # Create a view for the CSV file
            # auto_detect=True handles types
            # normalize_names=True might help with column mapping but let's stick to raw
            con.execute(
                f"CREATE OR REPLACE VIEW raw_logs AS SELECT * FROM '{safe_path}'"
            )

            # Get total count
            total_rows = con.execute(
                "SELECT COUNT(*) FROM raw_logs"
            ).fetchone()[0]
            logger.info(f"DuckDB: Identified {total_rows} rows")

            offset = 0
            while offset < total_rows:
                # fetch chunk
                # usage of .df() then .to_dict is standard
                result = con.execute(
                    f"SELECT * FROM raw_logs LIMIT {chunk_size} OFFSET {offset}"
                )
                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()

                # Convert to list of dicts manually
                chunk_data = []
                for row in rows:
                    # Convert row to dict
                    row_dict = dict(zip(columns, row))

                    # Manual fillna('') equivalent
                    for k, v in row_dict.items():
                        if v is None:
                            row_dict[k] = ""

                    chunk_data.append(row_dict)

                yield chunk_data
                offset += chunk_size

            con.close()

        except Exception as e:
            logger.warning(
                f"DuckDB Import optimization failed, falling back to standard CSV: {e}"
            )
            # Fallback to standard CSV reading
            import csv

            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                chunk = []
                for row in reader:
                    chunk.append(row)
                    if len(chunk) >= chunk_size:
                        yield chunk
                        chunk = []
                if chunk:
                    yield chunk

    async def get_or_create_station(self, callsign: str) -> int:
        """Retrieves or creates a Station by callsign.

        Args:
            callsign: The station identifier (will be uppercased).

        Returns:
            The station ID.
        """
        # Normalize to uppercase for case-insensitive matching
        callsign = callsign.upper().strip()

        if callsign in self.station_cache:
            return self.station_cache[callsign]

        stmt = select(Station).where(Station.callsign == callsign)
        result = await self.session.execute(stmt)
        station = result.scalar_one_or_none()

        if not station:
            station = Station(callsign=callsign)
            self.session.add(station)
            await self.session.flush()  # Get ID

        self.station_cache[callsign] = station.id
        return station.id

    async def process_batch(
        self,
        batch_id: int,
        logs: List[Dict[str, Any]],
        default_station: str = None,
    ) -> int:
        """Process a batch of logs. Optimizes matching by processing unique songs only."""
        # 1. Pre-process and Identify Unique Tuples
        # We need to map: "Original Row" -> "Unique Song"

        if not logs:
            return 0

        processed_rows = []
        unique_pairs = {}  # (raw_artist, raw_title) -> {original_indices: [], resolved_artist: str}

        # We need to resolve stations first as that's per-row
        # And parse dates

        valid_rows = []

        for idx, row in enumerate(logs):
            try:
                # Station
                callsign = row.get("Station", default_station) or "UNKNOWN"
                # Note: get_or_create_station is async, can't easily batch without refactor
                # But station caching makes it fast after first hit

                # Parsing logic
                played_at: Optional[datetime] = None

                # Try explicit 'Played' column first
                if "Played" in row:
                    played_at = parse_flexible_date(row["Played"])

                # Fallback to Date+Time columns
                if not played_at:
                    date_str = str(row.get("Date", ""))
                    time_str = str(row.get("Time", ""))
                    combined = f"{date_str} {time_str}".strip()
                    if date_str and time_str:
                        played_at = parse_flexible_date(combined)

                if not played_at:
                    # Log trace only to avoid spamming on header rows or empty lines
                    # logger.trace(f"Skipping row with invalid date: {row}")
                    continue

                raw_artist = str(row.get("Artist", "")).strip()
                raw_title = str(row.get("Title", "")).strip()

                if not raw_artist or not raw_title:
                    continue

                # Store valid row data
                row_data = {
                    "callsign": callsign,
                    "played_at": played_at,
                    "raw_artist": raw_artist,
                    "raw_title": raw_title,
                    "original_row": row,
                }
                valid_rows.append(row_data)

                # Add to unique set
                key = (raw_artist, raw_title)
                if key not in unique_pairs:
                    unique_pairs[key] = []
                unique_pairs[key].append(
                    len(valid_rows) - 1
                )  # Index in valid_rows

            except Exception:
                # logger.warning(f"Skipping row: {e}")
                continue

        if not valid_rows:
            return 0

        # 2. Bulk Resolve Stations (Optimization: gather unique callsigns)
        # For now, simplistic loop with cache is fine as stations count is low (usually 1)
        for row in valid_rows:
            row["station_id"] = await self.get_or_create_station(
                row["callsign"]
            )

        # 3. Identity Resolution on UNIQUE Artists
        # Turn ~50k rows into ~2k unique artists
        unique_raw_artists = list(set(k[0] for k in unique_pairs.keys()))
        resolved_artist_map = await self.identity_resolver.resolve_batch(
            unique_raw_artists
        )

        # 4. Prepare Match Queries for UNIQUE Pairs
        match_queries = []
        # We need to map (raw_artist, raw_title) -> (resolved_artist, raw_title)

        # We will iterate unique_pairs keys
        pair_to_resolved = {}  # (raw_a, raw_t) -> (resolved_a, raw_t)

        for ra, rt in unique_pairs.keys():
            resolved_a = resolved_artist_map.get(ra, ra)
            pair_to_resolved[(ra, rt)] = (resolved_a, rt)
            match_queries.append((resolved_a, rt))

        # 5. Bulk Match (The heavy lifter)
        # Now processing N=Unique Pairs instead of N=Total Rows
        match_results = await self.matcher.match_batch(match_queries)

        # 6. Map Results back to All Rows
        # Phase 4: match_batch now returns work_id (for bridge matches) or recording_id (for new matches)
        # We need to look up work_id for recording matches
        inserts = []
        recording_ids_to_lookup = set()
        
        for ra, rt in unique_pairs.keys():
            resolved_key = pair_to_resolved[(ra, rt)]
            match_id, match_reason = match_results.get(
                resolved_key, (None, "No Match Found")
            )
            if match_id is not None and "Identity Bridge" not in match_reason:
                # Non-bridge match returns recording_id, need to look up work_id
                recording_ids_to_lookup.add(match_id)
        
        # Batch fetch work_ids for recording matches
        recording_to_work = {}
        if recording_ids_to_lookup:
            rec_stmt = select(Recording.id, Recording.work_id).where(
                Recording.id.in_(list(recording_ids_to_lookup))
            )
            rec_result = await self.session.execute(rec_stmt)
            for rec_id, work_id in rec_result.all():
                recording_to_work[rec_id] = work_id
        
        for ra, rt in unique_pairs.keys():
            # Get match result for this pair
            resolved_key = pair_to_resolved[(ra, rt)]  # (resolved_a, rt)
            match_id, match_reason = match_results.get(
                resolved_key, (None, "No Match Found")
            )
            
            # Phase 4: Determine work_id
            work_id = None
            if match_id is not None:
                if "Identity Bridge" in match_reason:
                    # Bridge match already returns work_id
                    work_id = match_id
                else:
                    # Non-bridge match returns recording_id, look up work_id
                    work_id = recording_to_work.get(match_id)

            # Apply to all original rows that had this pair
            indices = unique_pairs[(ra, rt)]
            for idx in indices:
                row_data = valid_rows[idx]

                inserts.append(
                    {
                        "import_batch_id": batch_id,
                        "station_id": row_data["station_id"],
                        "played_at": row_data["played_at"],
                        "raw_artist": row_data["raw_artist"],
                        "raw_title": row_data["raw_title"],
                        "work_id": work_id,
                        "match_reason": match_reason,
                    }
                )

        # 7. Bulk Insert
        if inserts:
            matched = sum(1 for row in inserts if row["work_id"] is not None)
            unmatched = len(inserts) - matched
            logger.info(
                f"process_batch: batch_id={batch_id}, rows={len(inserts)}, "
                f"matched={matched}, unmatched={unmatched}"
            )
            # Chunk the inserts to avoid SQLite limits
            batch_size = 400
            for i in range(0, len(inserts), batch_size):
                chunk_data = inserts[i : i + batch_size]
                stmt = insert(BroadcastLog).values(chunk_data)
                await self.session.execute(stmt)

            await self.session.commit()

        return len(inserts)
