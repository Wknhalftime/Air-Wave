"""Recording Resolver service for the Three-Layer Identity Resolution architecture.

This service implements the Resolution Layer, which resolves a Work to a specific
Recording based on context and policies:
1. Station-specific preferences
2. Format-based preferences  
3. Work default recording
4. Any available recording (fallback)

The resolver ensures file availability before returning a recording, allowing
graceful fallback when preferred files are deleted or unavailable.

Typical usage:
    resolver = RecordingResolver(session)
    recording = await resolver.resolve(work_id=99, station_id=123)
"""

from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airwave.core.models import (
    FormatPreference,
    LibraryFile,
    Recording,
    Station,
    StationPreference,
    Work,
    WorkDefaultRecording,
)


class RecordingResolver:
    """Resolves a Work to a Recording based on context and policies.
    
    Resolution priority:
    1. Station-specific preference (if station_id provided)
    2. Format-based preference (if format_code provided)
    3. Work default recording
    4. Any available recording for the work
    
    Each level checks for file availability before selecting.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the resolver with a database session.
        
        Args:
            session: Async SQLAlchemy session for database operations.
        """
        self.session = session

    async def resolve(
        self,
        work_id: int,
        station_id: Optional[int] = None,
        format_code: Optional[str] = None,
    ) -> Optional[Recording]:
        """Resolve a Work to a Recording based on context and policies.
        
        Args:
            work_id: The Work ID to resolve.
            station_id: Optional station ID for station-specific preferences.
                If provided and no format_code is given, the station's format_code
                will be looked up automatically.
            format_code: Optional format code (e.g., 'AC', 'CHR') for format preferences.
                If not provided but station_id is, uses the station's format_code.
            
        Returns:
            The resolved Recording, or None if no recording is available.
        """
        # 1. Check station-specific preference
        if station_id:
            recording = await self._resolve_station_preference(station_id, work_id)
            if recording:
                logger.debug(
                    f"Resolved work_id={work_id} via station preference "
                    f"(station_id={station_id}) -> recording_id={recording.id}"
                )
                return recording

        # 2. Check format-based preference
        # If no format_code provided but station_id is, look up station's format
        effective_format_code = format_code
        if not effective_format_code and station_id:
            effective_format_code = await self._get_station_format_code(station_id)
        
        if effective_format_code:
            recording = await self._resolve_format_preference(effective_format_code, work_id)
            if recording:
                logger.debug(
                    f"Resolved work_id={work_id} via format preference "
                    f"(format_code={effective_format_code}) -> recording_id={recording.id}"
                )
                return recording

        # 3. Check work default recording
        recording = await self._resolve_work_default(work_id)
        if recording:
            logger.debug(
                f"Resolved work_id={work_id} via work default -> recording_id={recording.id}"
            )
            return recording

        # 4. Fallback: any available recording for the work
        recording = await self._get_any_available_recording(work_id)
        if recording:
            logger.debug(
                f"Resolved work_id={work_id} via fallback -> recording_id={recording.id}"
            )
        else:
            logger.warning(f"No available recording found for work_id={work_id}")
        
        return recording

    async def _get_station_format_code(self, station_id: int) -> Optional[str]:
        """Look up the format code for a station."""
        stmt = select(Station.format_code).where(Station.id == station_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _resolve_station_preference(
        self, station_id: int, work_id: int
    ) -> Optional[Recording]:
        """Look up station-specific recording preference."""
        stmt = (
            select(StationPreference)
            .where(
                StationPreference.station_id == station_id,
                StationPreference.work_id == work_id,
            )
            .order_by(StationPreference.priority)
            .options(selectinload(StationPreference.preferred_recording))
        )
        result = await self.session.execute(stmt)
        preferences = result.scalars().all()
        
        for pref in preferences:
            if await self._has_available_file(pref.preferred_recording_id):
                return pref.preferred_recording
        
        return None

    async def _resolve_format_preference(
        self, format_code: str, work_id: int
    ) -> Optional[Recording]:
        """Look up format-based recording preference."""
        stmt = (
            select(FormatPreference)
            .where(
                FormatPreference.format_code == format_code,
                FormatPreference.work_id == work_id,
            )
            .order_by(FormatPreference.priority)
            .options(selectinload(FormatPreference.preferred_recording))
        )
        result = await self.session.execute(stmt)
        preferences = result.scalars().all()
        
        for pref in preferences:
            if await self._has_available_file(pref.preferred_recording_id):
                return pref.preferred_recording
        
        return None

    async def _resolve_work_default(self, work_id: int) -> Optional[Recording]:
        """Look up work default recording."""
        stmt = (
            select(WorkDefaultRecording)
            .where(WorkDefaultRecording.work_id == work_id)
            .options(selectinload(WorkDefaultRecording.default_recording))
        )
        result = await self.session.execute(stmt)
        default = result.scalar_one_or_none()
        
        if default and await self._has_available_file(default.default_recording_id):
            return default.default_recording
        
        return None

    async def _get_any_available_recording(self, work_id: int) -> Optional[Recording]:
        """Get any recording for the work that has an available file.
        
        Prefers verified recordings over unverified ones.
        """
        # First try to get a verified recording with available file
        stmt = (
            select(Recording)
            .where(Recording.work_id == work_id, Recording.is_verified == True)
            .options(selectinload(Recording.files))
        )
        result = await self.session.execute(stmt)
        recordings = result.scalars().all()
        
        for rec in recordings:
            if await self._has_available_file(rec.id):
                return rec
        
        # Fall back to any recording with available file
        stmt = (
            select(Recording)
            .where(Recording.work_id == work_id)
            .options(selectinload(Recording.files))
        )
        result = await self.session.execute(stmt)
        recordings = result.scalars().all()
        
        for rec in recordings:
            if await self._has_available_file(rec.id):
                return rec
        
        # If no recording has a file, return the first recording anyway
        # (This handles "Silver" recordings that don't have library files)
        if recordings:
            return recordings[0]
        
        return None

    async def _has_available_file(self, recording_id: int) -> bool:
        """Check if a recording has at least one accessible library file.
        
        Args:
            recording_id: The recording ID to check.
            
        Returns:
            True if at least one library file exists for the recording.
        """
        stmt = select(LibraryFile.id).where(
            LibraryFile.recording_id == recording_id
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def resolve_for_broadcast_log(
        self,
        work_id: int,
        station_id: Optional[int] = None,
    ) -> Optional[Recording]:
        """Convenience method for resolving recordings for broadcast logs.
        
        This method is optimized for the common case of resolving a work
        to a recording when processing broadcast logs. It uses the station
        context if available.
        
        Args:
            work_id: The Work ID to resolve.
            station_id: Optional station ID from the broadcast log.
            
        Returns:
            The resolved Recording, or None if no recording is available.
        """
        # For broadcast logs, we don't typically have format_code
        # The station_id provides the context
        return await self.resolve(work_id=work_id, station_id=station_id)
