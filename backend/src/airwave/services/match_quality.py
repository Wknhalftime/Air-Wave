"""Match quality analysis utilities for the Match Tuner."""

from typing import List, Optional


def analyze_match_quality(
    raw_artist: str, raw_title: str, match_artist: str, match_title: str
) -> List[str]:
    """Analyze match quality and return warning flags for potentially problematic matches.

    Returns list of warning codes:
    - truncation_risk: Match is significantly shorter than original
    - length_mismatch: Significant length difference
    - extra_text: Match contains extra text (feat., remix, etc.)
    - case_only: Only difference is capitalization
    """
    warnings = []

    # Truncation risk: match is much shorter than original
    if len(match_title) < len(raw_title) * 0.6:
        warnings.append("truncation_risk")

    # Length mismatch: significant difference in length
    if abs(len(match_title) - len(raw_title)) > 30:
        warnings.append("length_mismatch")

    # Extra text indicators
    extra_text_patterns = [
        "feat.",
        "ft.",
        "(",
        "remix",
        "live",
        "version",
        "remaster",
        "edit",
    ]
    if any(p in match_title.lower() for p in extra_text_patterns):
        if not any(p in raw_title.lower() for p in extra_text_patterns):
            warnings.append("extra_text")

    # Case-only difference
    if raw_title.lower() == match_title.lower() and raw_title != match_title:
        warnings.append("case_only")

    return warnings


def detect_edge_case(
    artist_sim: float,
    title_sim: float,
    thresholds: dict,
    edge_threshold: float = 0.05,
) -> Optional[str]:
    """Detect if a match is near a threshold boundary (edge case).

    Returns edge case type if within edge_threshold (default 5%) of any threshold:
    - "near_auto_threshold": Either artist or title is within 5% of auto threshold
    - "near_review_threshold": Either artist or title is within 5% of review threshold

    Returns None if not an edge case.
    """
    artist_auto = thresholds["artist_auto"]
    title_auto = thresholds["title_auto"]
    artist_review = thresholds["artist_review"]
    title_review = thresholds["title_review"]

    # Check if near auto threshold (within 5% above or below)
    near_auto_artist = abs(artist_sim - artist_auto) <= edge_threshold
    near_auto_title = abs(title_sim - title_auto) <= edge_threshold

    if near_auto_artist or near_auto_title:
        return "near_auto_threshold"

    # Check if near review threshold (within 5% above or below)
    near_review_artist = abs(artist_sim - artist_review) <= edge_threshold
    near_review_title = abs(title_sim - title_review) <= edge_threshold

    if near_review_artist or near_review_title:
        return "near_review_threshold"

    return None
