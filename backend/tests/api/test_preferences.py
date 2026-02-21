"""Tests for the preferences API endpoints (Policy Layer)."""

import pytest
from httpx import AsyncClient

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


@pytest.fixture
async def test_data(db_session):
    """Create test data for preference tests."""
    artist = Artist(name="Test Artist")
    db_session.add(artist)
    await db_session.flush()

    work = Work(title="Test Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()

    rec_original = Recording(
        work_id=work.id, title="Test Song", version_type="Original"
    )
    rec_radio = Recording(
        work_id=work.id, title="Test Song (Radio Edit)", version_type="Radio Edit"
    )
    rec_live = Recording(
        work_id=work.id, title="Test Song (Live)", version_type="Live"
    )
    db_session.add_all([rec_original, rec_radio, rec_live])
    await db_session.flush()

    station = Station(callsign="WXYZ", format_code="AC")
    db_session.add(station)
    await db_session.flush()

    return {
        "artist": artist,
        "work": work,
        "rec_original": rec_original,
        "rec_radio": rec_radio,
        "rec_live": rec_live,
        "station": station,
    }


class TestStationPreferencesAPI:
    """Tests for station preference endpoints."""

    async def test_list_station_preferences_empty(
        self, async_client: AsyncClient, db_session
    ):
        """List returns empty when no preferences exist."""
        response = await async_client.get("/api/v1/preferences/stations")
        assert response.status_code == 200
        assert response.json() == []

    async def test_create_station_preference(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Can create a station preference."""
        response = await async_client.post(
            "/api/v1/preferences/stations",
            json={
                "station_id": test_data["station"].id,
                "work_id": test_data["work"].id,
                "preferred_recording_id": test_data["rec_radio"].id,
                "priority": 0,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["station_id"] == test_data["station"].id
        assert data["work_id"] == test_data["work"].id
        assert data["preferred_recording_id"] == test_data["rec_radio"].id
        assert data["station"]["callsign"] == "WXYZ"
        assert data["work"]["title"] == "Test Song"

    async def test_create_station_preference_invalid_station(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Returns 404 for invalid station."""
        response = await async_client.post(
            "/api/v1/preferences/stations",
            json={
                "station_id": 99999,
                "work_id": test_data["work"].id,
                "preferred_recording_id": test_data["rec_radio"].id,
            },
        )
        assert response.status_code == 404
        assert "Station" in response.json()["detail"]

    async def test_create_station_preference_recording_not_in_work(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Returns 400 if recording doesn't belong to work."""
        # Create another work with a recording
        other_work = Work(title="Other Song", artist_id=test_data["artist"].id)
        db_session.add(other_work)
        await db_session.flush()
        
        other_rec = Recording(work_id=other_work.id, title="Other Song")
        db_session.add(other_rec)
        await db_session.flush()

        response = await async_client.post(
            "/api/v1/preferences/stations",
            json={
                "station_id": test_data["station"].id,
                "work_id": test_data["work"].id,
                "preferred_recording_id": other_rec.id,
            },
        )
        assert response.status_code == 400
        assert "does not belong" in response.json()["detail"]

    async def test_list_station_preferences_filtered(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Can filter station preferences by station_id."""
        # Create preference
        pref = StationPreference(
            station_id=test_data["station"].id,
            work_id=test_data["work"].id,
            preferred_recording_id=test_data["rec_radio"].id,
        )
        db_session.add(pref)
        await db_session.flush()

        response = await async_client.get(
            f"/api/v1/preferences/stations?station_id={test_data['station'].id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["station_id"] == test_data["station"].id

    async def test_delete_station_preference(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Can delete a station preference."""
        pref = StationPreference(
            station_id=test_data["station"].id,
            work_id=test_data["work"].id,
            preferred_recording_id=test_data["rec_radio"].id,
        )
        db_session.add(pref)
        await db_session.flush()

        response = await async_client.delete(
            f"/api/v1/preferences/stations/{pref.id}"
        )
        assert response.status_code == 204

        # Verify deleted
        response = await async_client.get("/api/v1/preferences/stations")
        assert response.json() == []


class TestFormatPreferencesAPI:
    """Tests for format preference endpoints."""

    async def test_create_format_preference(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Can create a format preference."""
        response = await async_client.post(
            "/api/v1/preferences/formats",
            json={
                "format_code": "AC",
                "work_id": test_data["work"].id,
                "preferred_recording_id": test_data["rec_radio"].id,
                "exclude_tags": ["explicit"],
                "priority": 0,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["format_code"] == "AC"
        assert data["exclude_tags"] == ["explicit"]

    async def test_format_code_normalized_to_uppercase(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Format code is normalized to uppercase."""
        response = await async_client.post(
            "/api/v1/preferences/formats",
            json={
                "format_code": "chr",
                "work_id": test_data["work"].id,
                "preferred_recording_id": test_data["rec_radio"].id,
            },
        )
        assert response.status_code == 201
        assert response.json()["format_code"] == "CHR"

    async def test_list_format_preferences_by_format(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Can filter format preferences by format_code."""
        pref = FormatPreference(
            format_code="ROCK",
            work_id=test_data["work"].id,
            preferred_recording_id=test_data["rec_live"].id,
        )
        db_session.add(pref)
        await db_session.flush()

        response = await async_client.get(
            "/api/v1/preferences/formats?format_code=ROCK"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["format_code"] == "ROCK"

    async def test_delete_format_preference(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Can delete a format preference."""
        pref = FormatPreference(
            format_code="AC",
            work_id=test_data["work"].id,
            preferred_recording_id=test_data["rec_radio"].id,
        )
        db_session.add(pref)
        await db_session.flush()

        response = await async_client.delete(
            f"/api/v1/preferences/formats/{pref.id}"
        )
        assert response.status_code == 204


class TestWorkDefaultsAPI:
    """Tests for work default recording endpoints."""

    async def test_create_work_default(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Can create a work default recording."""
        response = await async_client.post(
            "/api/v1/preferences/defaults",
            json={
                "work_id": test_data["work"].id,
                "default_recording_id": test_data["rec_original"].id,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["work_id"] == test_data["work"].id
        assert data["default_recording_id"] == test_data["rec_original"].id

    async def test_update_work_default(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Creating a default for existing work updates it."""
        # Create initial default
        default = WorkDefaultRecording(
            work_id=test_data["work"].id,
            default_recording_id=test_data["rec_original"].id,
        )
        db_session.add(default)
        await db_session.flush()

        # Update to radio edit
        response = await async_client.post(
            "/api/v1/preferences/defaults",
            json={
                "work_id": test_data["work"].id,
                "default_recording_id": test_data["rec_radio"].id,
            },
        )
        assert response.status_code == 201
        assert response.json()["default_recording_id"] == test_data["rec_radio"].id

        # Verify only one default exists
        response = await async_client.get(
            f"/api/v1/preferences/defaults?work_id={test_data['work'].id}"
        )
        assert len(response.json()) == 1

    async def test_delete_work_default(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Can delete a work default recording."""
        default = WorkDefaultRecording(
            work_id=test_data["work"].id,
            default_recording_id=test_data["rec_original"].id,
        )
        db_session.add(default)
        await db_session.flush()

        response = await async_client.delete(
            f"/api/v1/preferences/defaults/{test_data['work'].id}"
        )
        assert response.status_code == 204


class TestFormatCodesAPI:
    """Tests for format codes utility endpoint."""

    async def test_list_format_codes(
        self, async_client: AsyncClient, db_session, test_data
    ):
        """Lists all distinct format codes."""
        # Add some format preferences
        pref1 = FormatPreference(
            format_code="AC",
            work_id=test_data["work"].id,
            preferred_recording_id=test_data["rec_radio"].id,
        )
        pref2 = FormatPreference(
            format_code="CHR",
            work_id=test_data["work"].id,
            preferred_recording_id=test_data["rec_radio"].id,
        )
        db_session.add_all([pref1, pref2])
        await db_session.flush()

        response = await async_client.get("/api/v1/preferences/formats/codes")
        assert response.status_code == 200
        codes = response.json()
        assert "AC" in codes
        assert "CHR" in codes

    async def test_format_codes_includes_station_formats(
        self, async_client: AsyncClient, db_session
    ):
        """Format codes includes station format_codes."""
        station = Station(callsign="KAAA", format_code="AAA")
        db_session.add(station)
        await db_session.flush()

        response = await async_client.get("/api/v1/preferences/formats/codes")
        assert response.status_code == 200
        assert "AAA" in response.json()
