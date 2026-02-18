from typing import Optional

from pydantic import BaseModel, ConfigDict


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
