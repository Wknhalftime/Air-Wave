"""Library models: Artist, Work, Recording, Album, LibraryFile."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airwave.core.models.base import Base, TimestampMixin


class Artist(Base, TimestampMixin):
    """Represents a musical creator (Individual or Group)."""

    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    musicbrainz_id: Mapped[Optional[str]] = mapped_column(
        String(36), unique=True, index=True, nullable=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )

    works: Mapped[List["Work"]] = relationship(
        secondary="work_artists", back_populates="artists"
    )
    primary_works: Mapped[List["Work"]] = relationship(back_populates="artist")
    albums: Mapped[List["Album"]] = relationship(back_populates="artist")


class Work(Base, TimestampMixin):
    """The abstract musical composition."""

    __tablename__ = "works"
    __table_args__ = (Index("idx_work_title_artist", "title", "artist_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, index=True)
    artist_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("artists.id"), nullable=True
    )
    is_instrumental: Mapped[bool] = mapped_column(Boolean, default=False)

    artist: Mapped[Optional["Artist"]] = relationship(
        back_populates="primary_works"
    )
    artists: Mapped[List["Artist"]] = relationship(
        secondary="work_artists", back_populates="works"
    )
    recordings: Mapped[List["Recording"]] = relationship(back_populates="work")


class WorkArtist(Base, TimestampMixin):
    """Bridge table associating Works with multiple Artists and Roles."""

    __tablename__ = "work_artists"

    work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id"), primary_key=True
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id"), primary_key=True
    )
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Album(Base, TimestampMixin):
    """A curated collection of Recordings."""

    __tablename__ = "albums"
    __table_args__ = (Index("idx_album_title_artist", "title", "artist_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, index=True)
    artist_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("artists.id"), nullable=True
    )
    release_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    artist: Mapped[Optional["Artist"]] = relationship(back_populates="albums")


class Recording(Base, TimestampMixin):
    """A specific recorded instance of a Work."""

    __tablename__ = "recordings"
    __table_args__ = (Index("idx_recording_work_title", "work_id", "title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"))
    title: Mapped[str] = mapped_column(String, index=True)
    version_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    isrc: Mapped[Optional[str]] = mapped_column(
        String, index=True, nullable=True
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    work: Mapped["Work"] = relationship(back_populates="recordings")
    files: Mapped[List["LibraryFile"]] = relationship(
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

    recording: Mapped["Recording"] = relationship(back_populates="files")
