from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin to add created_at and updated_at columns for auditing."""

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Artist(Base, TimestampMixin):
    """Represents a musical creator (Individual or Group)."""

    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    musicbrainz_id: Mapped[Optional[str]] = mapped_column(
        String(36), unique=True, index=True, nullable=True
    )

    # Relationships
    works: Mapped[List["Work"]] = relationship(
        secondary="work_artists", back_populates="artists"
    )
    primary_works: Mapped[List["Work"]] = relationship(back_populates="artist")
    albums: Mapped[List["Album"]] = relationship(back_populates="artist")


class Work(Base, TimestampMixin):
    """The abstract musical composition.

    Represents the song itself (the 'intent'), regardless of specific versions
    or recordings. E.g., 'Wonderwall' is the Work.
    """

    __tablename__ = "works"
    __table_args__ = (
        Index("idx_work_title_artist", "title", "artist_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, index=True)
    artist_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("artists.id"), nullable=True
    )  # Primary artist
    is_instrumental: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    artist: Mapped[Optional["Artist"]] = relationship(
        back_populates="primary_works"
    )
    artists: Mapped[List["Artist"]] = relationship(
        secondary="work_artists", back_populates="works"
    )
    recordings: Mapped[List["Recording"]] = relationship(back_populates="work")


class WorkArtist(Base, TimestampMixin):
    """Bridge table associating Works with multiple Artists and Roles.

    Enables tracking of main artists, featured artists, and collaborators.
    """

    __tablename__ = "work_artists"

    work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id"), primary_key=True
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id"), primary_key=True
    )
    role: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # e.g. "Main", "Featured"


class Album(Base, TimestampMixin):
    """A curated collection of Recordings."""

    __tablename__ = "albums"
    __table_args__ = (
        Index("idx_album_title_artist", "title", "artist_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, index=True)
    artist_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("artists.id"), nullable=True
    )  # Main artist or NULL for Various
    release_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # LP, EP, Single, Compilation

    # Relationships
    artist: Mapped[Optional["Artist"]] = relationship(back_populates="albums")


class Recording(Base, TimestampMixin):
    """A specific recorded instance of a Work.

    Distinct from the 'Work' as it includes version modifiers (Remix, Live, etc.)
    and technical metadata. This is the entity linked to play logs.
    """

    __tablename__ = "recordings"
    __table_args__ = (
        Index("idx_recording_work_title", "work_id", "title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"))
    title: Mapped[str] = mapped_column(String, index=True)  # Version title
    version_type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Live, Remix, etc.
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    isrc: Mapped[Optional[str]] = mapped_column(
        String, index=True, nullable=True
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    work: Mapped["Work"] = relationship(back_populates="recordings")
    files: Mapped[List["LibraryFile"]] = relationship(
        back_populates="recording"
    )
    broadcast_logs: Mapped[List["BroadcastLog"]] = relationship(
        back_populates="recording"
    )


class LibraryFile(Base, TimestampMixin):
    """The physical audio file stored on disk."""

    __tablename__ = "library_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    recording_id: Mapped[int] = mapped_column(ForeignKey("recordings.id"))
    path: Mapped[str] = mapped_column(String, unique=True, index=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String, index=True)
    size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mtime: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bitrate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    recording: Mapped["Recording"] = relationship(back_populates="files")


class Station(Base, TimestampMixin):
    """A broadcasting station providing playlist logs."""

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    callsign: Mapped[str] = mapped_column(String, unique=True)
    frequency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    broadcast_logs: Mapped[List["BroadcastLog"]] = relationship(
        back_populates="station"
    )


class BroadcastLog(Base, TimestampMixin):
    """An individual play-event extracted from a station log."""

    __tablename__ = "broadcast_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    played_at: Mapped[datetime] = mapped_column(index=True)
    raw_artist: Mapped[str] = mapped_column(String)
    raw_title: Mapped[str] = mapped_column(String)

    # Link to the verified library Recording
    recording_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("recordings.id"), nullable=True, index=True
    )

    import_batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("import_batches.id"), nullable=True
    )
    match_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    station: Mapped["Station"] = relationship(back_populates="broadcast_logs")
    recording: Mapped[Optional["Recording"]] = relationship(
        back_populates="broadcast_logs"
    )
    import_batch: Mapped[Optional["ImportBatch"]] = relationship(
        back_populates="logs"
    )

    # Composite index for performance-critical time-range queries
    __table_args__ = (
        Index("idx_broadcast_station_time", "station_id", "played_at"),
    )


class IdentityBridge(Base, TimestampMixin):
    """A cache of verified (Raw String) -> (Recording ID) mappings.

    Acts as the system's 'memory' to skip complex matching for recurring logs.
    """

    __tablename__ = "identity_bridge"

    id: Mapped[int] = mapped_column(primary_key=True)
    log_signature: Mapped[str] = mapped_column(
        String, unique=True, index=True
    )  # Hash(raw_artist|raw_title)
    reference_artist: Mapped[str] = mapped_column(String)  # For human review
    reference_title: Mapped[str] = mapped_column(String)

    recording_id: Mapped[int] = mapped_column(ForeignKey("recordings.id"))
    confidence: Mapped[float] = mapped_column(default=1.0)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    recording: Mapped["Recording"] = relationship()


class VerificationAudit(Base, TimestampMixin):
    """Audit trail for verification actions (link, promote, undo, etc.)."""

    __tablename__ = "verification_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_type: Mapped[str] = mapped_column(String, index=True)
    signature: Mapped[str] = mapped_column(String, index=True)
    raw_artist: Mapped[str] = mapped_column(String, index=True)
    raw_title: Mapped[str] = mapped_column(String, index=True)
    recording_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("recordings.id"), nullable=True, index=True
    )
    log_ids: Mapped[list] = mapped_column(JSON, default=list)
    bridge_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("identity_bridge.id"), nullable=True, index=True
    )
    is_undone: Mapped[bool] = mapped_column(Boolean, default=False)
    undone_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    performed_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    recording: Mapped[Optional["Recording"]] = relationship()
    bridge: Mapped[Optional["IdentityBridge"]] = relationship()

    __table_args__ = (
        Index("idx_verification_audit_created_at", "created_at"),
        Index("idx_verification_audit_artist_title", "raw_artist", "raw_title"),
    )


class ImportBatch(Base, TimestampMixin):
    """Tracks the status and progress of bulk log ingestion tasks."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(
        String, default="PENDING"
    )  # PENDING, PROCESSING, COMPLETED, FAILED
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    logs: Mapped[List["BroadcastLog"]] = relationship(
        back_populates="import_batch"
    )


class SystemSetting(Base, TimestampMixin):
    """Persistent storage for dynamic application settings."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class ArtistAlias(Base, TimestampMixin):
    """Normalized mapping of raw log names to canonical library names."""

    __tablename__ = "artist_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_name: Mapped[str] = mapped_column(String, unique=True, index=True)
    resolved_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Validation Flags
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_null: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Cache for 'Not Found' results


class ProposedSplit(Base, TimestampMixin):
    """Pending artist collaboration splits awaiting human approval.

    Created when ambiguous separators (e.g., '/') are found in log metadata.
    """

    __tablename__ = "proposed_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_artist: Mapped[str] = mapped_column(String, unique=True, index=True)

    # JSON list of candidates: ["Artist 1", "Artist 2"]
    proposed_artists: Mapped[list] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(
        String, default="PENDING"
    )  # PENDING, APPROVED, REJECTED
    confidence: Mapped[float] = mapped_column(default=0.0)


class DiscoveryQueue(Base, TimestampMixin):
    """Aggregation layer for unmatched logs.

    Acts as the 'Inbox' for the Verification Hub. Instead of creating thousands
    of 'Ghost Rankings', we aggregate unmatched signatures here.
    """

    __tablename__ = "discovery_queue"

    signature: Mapped[str] = mapped_column(String, primary_key=True)
    raw_artist: Mapped[str] = mapped_column(String)
    raw_title: Mapped[str] = mapped_column(String)
    count: Mapped[int] = mapped_column(Integer, default=1)
    
    # If the system identifies a potential existing match, it suggests it here.
    suggested_recording_id: Mapped[Optional[int]] = mapped_column(
         ForeignKey("recordings.id"), nullable=True
    )
    
    # Relationships
    suggested_recording: Mapped[Optional["Recording"]] = relationship()
