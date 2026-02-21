"""Broadcast models: Station, BroadcastLog, ImportBatch."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airwave.core.models.base import Base, TimestampMixin
from airwave.core.models.library import Work


class Station(Base, TimestampMixin):
    """A broadcasting station providing playlist logs."""

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    callsign: Mapped[str] = mapped_column(String, unique=True)
    frequency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    format_code: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )

    broadcast_logs: Mapped[List["BroadcastLog"]] = relationship(
        back_populates="station"
    )


class ImportBatch(Base, TimestampMixin):
    """Tracks the status and progress of bulk log ingestion tasks."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    logs: Mapped[List["BroadcastLog"]] = relationship(
        back_populates="import_batch"
    )


class BroadcastLog(Base, TimestampMixin):
    """An individual play-event extracted from a station log."""

    __tablename__ = "broadcast_logs"
    __table_args__ = (
        Index("idx_broadcast_station_time", "station_id", "played_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    played_at: Mapped[datetime] = mapped_column(index=True)
    raw_artist: Mapped[str] = mapped_column(String)
    raw_title: Mapped[str] = mapped_column(String)
    work_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("works.id"), nullable=True, index=True
    )
    import_batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("import_batches.id"), nullable=True
    )
    match_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    station: Mapped["Station"] = relationship(back_populates="broadcast_logs")
    work: Mapped[Optional["Work"]] = relationship()
    import_batch: Mapped[Optional["ImportBatch"]] = relationship(
        back_populates="logs"
    )
