"""Tests for the RecordingResolver service (Phase 3 of Identity Resolution)."""

import pytest
from sqlalchemy import select

from airwave.core.models import (
    Artist,
    FormatPreference,
    LibraryFile,
    Recording,
    Station,
    StationPreference,
    Work,
    WorkDefaultRecording,
)
from airwave.worker.recording_resolver import RecordingResolver


@pytest.fixture
async def resolver(db_session):
    """Create a RecordingResolver instance."""
    return RecordingResolver(db_session)


@pytest.fixture
async def test_work_with_recordings(db_session):
    """Create a work with multiple recordings for testing resolution."""
    artist = Artist(name="Test Artist")
    db_session.add(artist)
    await db_session.flush()

    work = Work(title="Test Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()

    # Create multiple recordings for the same work
    rec_original = Recording(
        work_id=work.id, title="Test Song", version_type="Original", is_verified=True
    )
    rec_live = Recording(
        work_id=work.id, title="Test Song (Live)", version_type="Live", is_verified=True
    )
    rec_radio = Recording(
        work_id=work.id,
        title="Test Song (Radio Edit)",
        version_type="Radio Edit",
        is_verified=True,
    )
    db_session.add_all([rec_original, rec_live, rec_radio])
    await db_session.flush()

    # Create library files for the recordings (except rec_live to test fallback)
    lf_original = LibraryFile(
        recording_id=rec_original.id,
        path="/music/test_song.mp3",
    )
    lf_radio = LibraryFile(
        recording_id=rec_radio.id,
        path="/music/test_song_radio.mp3",
    )
    db_session.add_all([lf_original, lf_radio])
    await db_session.flush()

    return {
        "artist": artist,
        "work": work,
        "rec_original": rec_original,
        "rec_live": rec_live,
        "rec_radio": rec_radio,
    }


@pytest.fixture
async def test_station(db_session):
    """Create a test station."""
    station = Station(callsign="WXYZ")
    db_session.add(station)
    await db_session.flush()
    return station


@pytest.fixture
async def test_station_with_format(db_session):
    """Create a test station with format_code."""
    station = Station(callsign="KABC", format_code="AC")
    db_session.add(station)
    await db_session.flush()
    return station


class TestRecordingResolver:
    """Test the RecordingResolver service."""

    async def test_resolve_fallback_to_any_recording(
        self, db_session, resolver, test_work_with_recordings
    ):
        """When no preferences exist, resolve to any available recording."""
        work = test_work_with_recordings["work"]
        rec_original = test_work_with_recordings["rec_original"]

        recording = await resolver.resolve(work_id=work.id)

        assert recording is not None
        # Should return one of the recordings with available files
        assert recording.id in [
            test_work_with_recordings["rec_original"].id,
            test_work_with_recordings["rec_radio"].id,
        ]

    async def test_resolve_station_preference(
        self, db_session, resolver, test_work_with_recordings, test_station
    ):
        """Station preference should override default resolution."""
        work = test_work_with_recordings["work"]
        rec_radio = test_work_with_recordings["rec_radio"]

        # Set station preference for radio edit
        pref = StationPreference(
            station_id=test_station.id,
            work_id=work.id,
            preferred_recording_id=rec_radio.id,
            priority=0,
        )
        db_session.add(pref)
        await db_session.flush()

        recording = await resolver.resolve(work_id=work.id, station_id=test_station.id)

        assert recording is not None
        assert recording.id == rec_radio.id

    async def test_resolve_station_preference_fallback_on_missing_file(
        self, db_session, resolver, test_work_with_recordings, test_station
    ):
        """If preferred recording has no file, fallback to next option."""
        work = test_work_with_recordings["work"]
        rec_live = test_work_with_recordings["rec_live"]  # No library file
        rec_original = test_work_with_recordings["rec_original"]

        # Set station preference for live version (which has no file)
        pref = StationPreference(
            station_id=test_station.id,
            work_id=work.id,
            preferred_recording_id=rec_live.id,
            priority=0,
        )
        db_session.add(pref)
        await db_session.flush()

        recording = await resolver.resolve(work_id=work.id, station_id=test_station.id)

        # Should fallback since rec_live has no file
        assert recording is not None
        assert recording.id != rec_live.id

    async def test_resolve_format_preference(
        self, db_session, resolver, test_work_with_recordings
    ):
        """Format preference should be used when no station preference exists."""
        work = test_work_with_recordings["work"]
        rec_radio = test_work_with_recordings["rec_radio"]

        # Set format preference for AC stations to prefer radio edit
        pref = FormatPreference(
            format_code="AC",
            work_id=work.id,
            preferred_recording_id=rec_radio.id,
            priority=0,
        )
        db_session.add(pref)
        await db_session.flush()

        recording = await resolver.resolve(work_id=work.id, format_code="AC")

        assert recording is not None
        assert recording.id == rec_radio.id

    async def test_resolve_work_default(
        self, db_session, resolver, test_work_with_recordings
    ):
        """Work default should be used when no station/format preference exists."""
        work = test_work_with_recordings["work"]
        rec_radio = test_work_with_recordings["rec_radio"]

        # Set work default to radio edit
        default = WorkDefaultRecording(
            work_id=work.id, default_recording_id=rec_radio.id
        )
        db_session.add(default)
        await db_session.flush()

        recording = await resolver.resolve(work_id=work.id)

        assert recording is not None
        assert recording.id == rec_radio.id

    async def test_resolve_priority_order(
        self, db_session, resolver, test_work_with_recordings, test_station
    ):
        """Station preference should take priority over format and default."""
        work = test_work_with_recordings["work"]
        rec_original = test_work_with_recordings["rec_original"]
        rec_radio = test_work_with_recordings["rec_radio"]

        # Set all three preferences to different recordings
        station_pref = StationPreference(
            station_id=test_station.id,
            work_id=work.id,
            preferred_recording_id=rec_original.id,
            priority=0,
        )
        format_pref = FormatPreference(
            format_code="AC",
            work_id=work.id,
            preferred_recording_id=rec_radio.id,
            priority=0,
        )
        default = WorkDefaultRecording(
            work_id=work.id, default_recording_id=rec_radio.id
        )
        db_session.add_all([station_pref, format_pref, default])
        await db_session.flush()

        # With station_id, should use station preference
        recording = await resolver.resolve(
            work_id=work.id, station_id=test_station.id, format_code="AC"
        )
        assert recording.id == rec_original.id

    async def test_resolve_nonexistent_work(self, db_session, resolver):
        """Resolving a nonexistent work should return None."""
        recording = await resolver.resolve(work_id=99999)
        assert recording is None

    async def test_resolve_for_broadcast_log(
        self, db_session, resolver, test_work_with_recordings, test_station
    ):
        """Test the convenience method for broadcast log resolution."""
        work = test_work_with_recordings["work"]
        rec_radio = test_work_with_recordings["rec_radio"]

        # Set station preference
        pref = StationPreference(
            station_id=test_station.id,
            work_id=work.id,
            preferred_recording_id=rec_radio.id,
            priority=0,
        )
        db_session.add(pref)
        await db_session.flush()

        recording = await resolver.resolve_for_broadcast_log(
            work_id=work.id, station_id=test_station.id
        )

        assert recording is not None
        assert recording.id == rec_radio.id

    async def test_resolve_auto_format_from_station(
        self, db_session, resolver, test_work_with_recordings, test_station_with_format
    ):
        """Station's format_code is used automatically for format preference lookup."""
        work = test_work_with_recordings["work"]
        rec_radio = test_work_with_recordings["rec_radio"]

        # Set format preference for AC format (matches station's format_code)
        format_pref = FormatPreference(
            format_code="AC",
            work_id=work.id,
            preferred_recording_id=rec_radio.id,
            priority=0,
        )
        db_session.add(format_pref)
        await db_session.flush()

        # Pass only station_id - format_code should be looked up automatically
        recording = await resolver.resolve(
            work_id=work.id, station_id=test_station_with_format.id
        )

        assert recording is not None
        assert recording.id == rec_radio.id

    async def test_resolve_explicit_format_overrides_station_format(
        self, db_session, resolver, test_work_with_recordings, test_station_with_format
    ):
        """Explicit format_code parameter overrides station's format_code."""
        work = test_work_with_recordings["work"]
        rec_original = test_work_with_recordings["rec_original"]
        rec_radio = test_work_with_recordings["rec_radio"]

        # AC format prefers radio
        ac_pref = FormatPreference(
            format_code="AC",
            work_id=work.id,
            preferred_recording_id=rec_radio.id,
            priority=0,
        )
        # ROCK format prefers original
        rock_pref = FormatPreference(
            format_code="ROCK",
            work_id=work.id,
            preferred_recording_id=rec_original.id,
            priority=0,
        )
        db_session.add_all([ac_pref, rock_pref])
        await db_session.flush()

        # Station is AC but we explicitly request ROCK format
        recording = await resolver.resolve(
            work_id=work.id, station_id=test_station_with_format.id, format_code="ROCK"
        )

        assert recording is not None
        assert recording.id == rec_original.id
