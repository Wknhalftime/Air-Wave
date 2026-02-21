#!/usr/bin/env python3
"""Parse large-scale radio CSV logs into Artist -> Song -> Playtimes model.

Implements a Master Catalog strategy with decoupled phases:
  Phase A: Build unique (Artist, Title, Year) Song Catalog
  Phase B: Map timestamps to Song IDs (Airplay Log)

Uses vectorized Polars processing for memory efficiency and speed.
Expects CSV columns: [Station, Played, Artist, Title, Release Year, Grc].

Usage:
    poetry run python -m airwave.scripts.parse_radio_logs path/to/radio_log.csv -o output_dir
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

from airwave.core.normalization import Normalizer


EXPECTED_COLUMNS = {"Station", "Played", "Artist", "Title", "Release Year", "Grc"}


def parse_radio_logs(
    input_path: Path,
    output_dir: Path,
    *,
    chunk_size: int | None = None,
) -> tuple[Path, Path]:
    """Parse radio CSV into Song Catalog and Airplay Log.

    Phase A: Build unique (Artist, Title, Year) catalog
    Phase B: Map Played timestamps to Song ID
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if chunk_size:
        lf = pl.scan_csv(input_path, infer_schema_length=10000)
        df = lf.head(chunk_size).collect()
    else:
        df = pl.read_csv(input_path, infer_schema_length=10000)

    cols = {c.strip(): c for c in df.columns}
    rename_map = {}
    for want in EXPECTED_COLUMNS:
        for k, v in cols.items():
            if k.lower().replace(" ", "_") == want.lower().replace(" ", "_"):
                rename_map[v] = want
                break
    if rename_map:
        df = df.rename(rename_map)

    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.with_columns(
        pl.col("Artist")
        .map_elements(
            lambda x: Normalizer.split_artists(str(x))[0] if x else "",
            return_dtype=pl.Utf8,
        )
        .alias("artist_normalized")
    )

    df = df.with_columns(
        pl.col("Title")
        .map_elements(
            lambda x: Normalizer.clean(str(x)) if x else "",
            return_dtype=pl.Utf8,
        )
        .alias("title_normalized")
    ).with_columns(
        pl.when(pl.col("Release Year").is_null())
        .then(None)
        .otherwise(
            pl.col("Release Year")
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.extract(r"(\d{4})", 1)
            .cast(pl.Int32)
        )
        .alias("year")
    )

    SENTINEL_YEAR = -1
    df = df.with_columns(pl.col("year").fill_null(SENTINEL_YEAR).alias("year_join"))
    catalog_df = (
        df.select(["artist_normalized", "title_normalized", "year_join"])
        .unique()
        .sort(["artist_normalized", "title_normalized"])
    )
    catalog_df = catalog_df.with_row_index("song_id", offset=1)
    catalog_for_join = catalog_df.select(
        ["artist_normalized", "title_normalized", "year_join", "song_id"]
    )
    catalog_df = catalog_df.with_columns(
        pl.when(pl.col("year_join") == SENTINEL_YEAR)
        .then(None)
        .otherwise(pl.col("year_join"))
        .alias("year")
    ).select(["song_id", "artist_normalized", "title_normalized", "year"])
    catalog_df = catalog_df.rename(
        {"artist_normalized": "artist", "title_normalized": "title"}
    )

    df = df.join(
        catalog_for_join,
        on=["artist_normalized", "title_normalized", "year_join"],
        how="left",
    )

    airplay_df = df.select(
        pl.col("Played").alias("timestamp"),
        pl.col("song_id"),
    )

    catalog_path = output_dir / "song_catalog.csv"
    airplay_path = output_dir / "airplay_log.csv"
    catalog_df.write_csv(catalog_path)
    airplay_df.write_csv(airplay_path)

    return catalog_path, airplay_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse radio CSV logs into Song Catalog and Airplay Log."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to input CSV (columns: Station, Played, Artist, Title, Release Year, Grc)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Output directory for song_catalog.csv and airplay_log.csv (default: current dir)",
    )
    parser.add_argument(
        "--chunk",
        type=int,
        default=None,
        help="Process only first N rows (for testing or memory limits)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        catalog_path, airplay_path = parse_radio_logs(
            args.input, args.output_dir, chunk_size=args.chunk
        )
        print(f"Song Catalog: {catalog_path}")
        print(f"Airplay Log:  {airplay_path}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
