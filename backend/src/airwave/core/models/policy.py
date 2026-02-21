"""Policy models: StationPreference, FormatPreference, WorkDefaultRecording."""

from sqlalchemy import ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airwave.core.models.base import Base, TimestampMixin
from airwave.core.models.broadcast import Station
from airwave.core.models.library import Recording, Work


class StationPreference(Base, TimestampMixin):
    """Station-specific recording preferences for a work."""

    __tablename__ = "station_preferences"
    __table_args__ = (Index("idx_station_pref_lookup", "station_id", "work_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    preferred_recording_id: Mapped[int] = mapped_column(
        ForeignKey("recordings.id")
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)

    station: Mapped["Station"] = relationship()
    work: Mapped["Work"] = relationship()
    preferred_recording: Mapped["Recording"] = relationship()


class FormatPreference(Base, TimestampMixin):
    """Format-based recording preferences."""

    __tablename__ = "format_preferences"
    __table_args__ = (Index("idx_format_pref_lookup", "format_code", "work_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    format_code: Mapped[str] = mapped_column(String, index=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    preferred_recording_id: Mapped[int] = mapped_column(
        ForeignKey("recordings.id")
    )
    exclude_tags: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    work: Mapped["Work"] = relationship()
    preferred_recording: Mapped["Recording"] = relationship()


class WorkDefaultRecording(Base, TimestampMixin):
    """Global default recording for a work when no other preference applies."""

    __tablename__ = "work_default_recordings"

    work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id"), primary_key=True
    )
    default_recording_id: Mapped[int] = mapped_column(
        ForeignKey("recordings.id")
    )

    work: Mapped["Work"] = relationship()
    default_recording: Mapped["Recording"] = relationship()
