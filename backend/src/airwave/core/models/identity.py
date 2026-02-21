"""Identity models: IdentityBridge, VerificationAudit, ArtistAlias, ProposedSplit, DiscoveryQueue."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airwave.core.models.base import Base, TimestampMixin
from airwave.core.models.library import Recording, Work


class IdentityBridge(Base, TimestampMixin):
    """A cache of verified (Raw String) -> (Work ID) mappings."""

    __tablename__ = "identity_bridge"

    id: Mapped[int] = mapped_column(primary_key=True)
    log_signature: Mapped[str] = mapped_column(
        String, unique=True, index=True
    )
    reference_artist: Mapped[str] = mapped_column(String)
    reference_title: Mapped[str] = mapped_column(String)
    work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id"), index=True
    )
    confidence: Mapped[float] = mapped_column(default=1.0)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    work: Mapped["Work"] = relationship()


class VerificationAudit(Base, TimestampMixin):
    """Audit trail for verification actions."""

    __tablename__ = "verification_audit"
    __table_args__ = (
        Index("idx_verification_audit_created_at", "created_at"),
        Index("idx_verification_audit_artist_title", "raw_artist", "raw_title"),
    )

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


class ArtistAlias(Base, TimestampMixin):
    """Normalized mapping of raw log names to canonical library names."""

    __tablename__ = "artist_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_name: Mapped[str] = mapped_column(String, unique=True, index=True)
    resolved_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_null: Mapped[bool] = mapped_column(Boolean, default=False)


class ProposedSplit(Base, TimestampMixin):
    """Pending artist collaboration splits awaiting human approval."""

    __tablename__ = "proposed_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_artist: Mapped[str] = mapped_column(String, unique=True, index=True)
    proposed_artists: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    confidence: Mapped[float] = mapped_column(default=0.0)


class DiscoveryQueue(Base, TimestampMixin):
    """Aggregation layer for unmatched logs."""

    __tablename__ = "discovery_queue"

    signature: Mapped[str] = mapped_column(String, primary_key=True)
    raw_artist: Mapped[str] = mapped_column(String)
    raw_title: Mapped[str] = mapped_column(String)
    count: Mapped[int] = mapped_column(Integer, default=1)
    suggested_work_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("works.id"), nullable=True
    )

    suggested_work: Mapped[Optional["Work"]] = relationship()
