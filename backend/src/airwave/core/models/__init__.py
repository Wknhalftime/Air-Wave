"""SQLAlchemy models for the Airwave application.

Submodules:
- base: Base, TimestampMixin
- library: Artist, Work, WorkArtist, Album, Recording, LibraryFile
- broadcast: Station, BroadcastLog, ImportBatch
- identity: IdentityBridge, VerificationAudit, ArtistAlias, ProposedSplit, DiscoveryQueue
- policy: StationPreference, FormatPreference, WorkDefaultRecording
- system: SystemSetting
"""

from airwave.core.models.base import Base, TimestampMixin
from airwave.core.models.library import (
    Album,
    Artist,
    LibraryFile,
    Recording,
    Work,
    WorkArtist,
)
from airwave.core.models.broadcast import (
    BroadcastLog,
    ImportBatch,
    Station,
)
from airwave.core.models.identity import (
    ArtistAlias,
    DiscoveryQueue,
    IdentityBridge,
    ProposedSplit,
    VerificationAudit,
)
from airwave.core.models.policy import (
    FormatPreference,
    StationPreference,
    WorkDefaultRecording,
)
from airwave.core.models.system import SystemSetting

__all__ = [
    "Base",
    "TimestampMixin",
    "Artist",
    "Work",
    "WorkArtist",
    "Album",
    "Recording",
    "LibraryFile",
    "Station",
    "BroadcastLog",
    "ImportBatch",
    "IdentityBridge",
    "VerificationAudit",
    "ArtistAlias",
    "ProposedSplit",
    "DiscoveryQueue",
    "StationPreference",
    "FormatPreference",
    "WorkDefaultRecording",
    "SystemSetting",
]
