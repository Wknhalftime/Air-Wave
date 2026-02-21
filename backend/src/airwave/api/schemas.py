from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# Match Tuner schemas
class MatchCandidate(BaseModel):
    """Single match candidate with quality analysis."""
    recording_id: int
    artist: str
    title: str
    artist_sim: float
    title_sim: float
    vector_dist: float
    match_type: str
    quality_warnings: List[str] = []
    edge_case: Optional[str] = None


class MatchSample(BaseModel):
    """Sample of unmatched log with match candidates."""
    id: int
    raw_artist: str
    raw_title: str
    match: Optional[dict]
    candidates: List[MatchCandidate]
    category: Optional[str] = None
    action: Optional[str] = None


class MatchImpactResponse(BaseModel):
    """Response model for match impact analysis."""
    total_unmatched: int
    sample_size: int
    auto_link_count: int
    auto_link_percentage: float
    review_count: int
    review_percentage: float
    reject_count: int
    reject_percentage: float
    identity_bridge_count: int
    identity_bridge_percentage: float
    edge_cases: dict
    thresholds_used: dict


class ThresholdSettings(BaseModel):
    """Matching threshold configuration."""
    artist_auto: float
    artist_review: float
    title_auto: float
    title_review: float


class ArtistStats(BaseModel):
    """Artist with aggregated statistics for library grid."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    work_count: int
    recording_count: int
    avatar_url: Optional[str] = None


class ArtistDetail(BaseModel):
    """Detailed artist information for artist detail page."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    musicbrainz_id: Optional[str] = None
    work_count: Optional[int] = None
    recording_count: Optional[int] = None


class WorkListItem(BaseModel):
    """Work summary for display in artist detail page grid."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist_names: str  # Comma-separated artist names (e.g., "Queen, David Bowie")
    recording_count: int
    duration_total: Optional[float] = None  # Total duration of all recordings in seconds
    year: Optional[int] = None  # Year of first recording (optional)


class WorkDetail(BaseModel):
    """Detailed work information for work detail page header."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist_id: Optional[int] = None
    artist_name: Optional[str] = None  # Primary artist name
    artist_names: str  # All artist names (e.g., "Queen, David Bowie")
    is_instrumental: bool
    recording_count: Optional[int] = None


class RecordingListItem(BaseModel):
    """Recording information for display in work detail page table."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist_display: str  # Artist name(s) for this recording
    duration: Optional[float] = None  # Duration in seconds
    version_type: Optional[str] = None  # Live, Remix, etc.
    work_title: str  # Work title for the "Work" column
    is_verified: bool  # Matched/Unmatched status
    has_file: bool  # Whether recording has associated library file (Library/Metadata only)
    filename: Optional[str] = None  # Filename (not full path) from first library file
