from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger


def parse_flexible_date(value: Any) -> Optional[datetime]:
    """Parses a date string from various common formats.

    Args:
        value: The input value (string, datetime, etc.) to parsing.

    Returns:
        A timezone-aware datetime object (UTC) or None if parsing fails.
    """
    if not value:
        return None

    if isinstance(value, datetime):
        # Ensure timezone awareness
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    value_str = str(value).strip()
    if not value_str or value_str.lower() in ["none", "null", "nan"]:
        return None

    # Common formats found in station logs
    formats = [
        "%Y-%m-%d %H:%M:%S",  # ISO-like: 2023-01-01 12:00:00
        "%m/%d/%Y %H:%M:%S",  # US format: 01/01/2023 12:00:00
        "%Y-%m-%dT%H:%M:%S",  # ISO strict
        "%Y-%m-%d",  # Date only
        "%m/%d/%Y",  # US Date only
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value_str, fmt)
            # Assyume mostly UTC/Local naive logs -> treat as UTC for consistency
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    logger.warning(f"Failed to parse date: '{value_str}'")
    return None


def guess_station_from_filename(filename: str) -> str:
    """Heuristic to guess station callsign from a filename.

    Strategies:
    1. Take first part before underscore or hyphen.
    2. Fallback to 'UNKNOWN' if ambiguous.

    Args:
        filename: The basename of the file (e.g. "KROQ_2023.csv").

    Returns:
        Uppercased callsign string or 'UNKNOWN'.
    """
    if not filename:
        return "UNKNOWN"

    # Infer Station from Filename Strategy:
    # 1. Take first part before underscore or hyphen
    # e.g., "KROQ_2004.csv" -> "KROQ"
    # e.g., "KIIS-FM Log.csv" -> "KIIS"
    station_guess = filename.split("_")[0].split("-")[0].split(" ")[0].upper()

    # Sanity check: if guess is empty or numeric, fallback to 'UNKNOWN'
    if not station_guess or station_guess.isdigit():
        return "UNKNOWN"

    return station_guess
