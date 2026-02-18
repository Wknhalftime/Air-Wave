"""
Integration tests for library navigation flow.

Tests the complete user journey:
1. View artist list
2. Click artist → view artist detail with works
3. Click work → view work detail with recordings
4. Apply filters and pagination
"""

import pytest
from airwave.core.models import Artist, Work, WorkArtist, Recording, LibraryFile


@pytest.mark.asyncio
async def test_library_navigation_full_flow(client, db_session):
    """
    Test the complete library navigation flow:
    Artist List → Artist Detail → Work Detail → Recordings
    """
    # ========================================================================
    # Setup: Create a realistic library structure
    # ========================================================================

    # Create artists
    queen = Artist(name="Queen", musicbrainz_id="0383dadf-2a4e-4d10-a46a-e9e041da8eb3")
    bowie = Artist(name="David Bowie", musicbrainz_id="5441c29d-3602-4898-b1a1-b77fa23b8e50")
    db_session.add_all([queen, bowie])
    await db_session.flush()

    # Create works
    bohemian = Work(title="Bohemian Rhapsody", artist_id=queen.id, is_instrumental=False)
    pressure = Work(title="Under Pressure", artist_id=queen.id, is_instrumental=False)
    db_session.add_all([bohemian, pressure])
    await db_session.flush()

    # Add work-artist relationships
    wa_bohemian = WorkArtist(work_id=bohemian.id, artist_id=queen.id)
    wa_pressure_queen = WorkArtist(work_id=pressure.id, artist_id=queen.id)
    wa_pressure_bowie = WorkArtist(work_id=pressure.id, artist_id=bowie.id)
    db_session.add_all([wa_bohemian, wa_pressure_queen, wa_pressure_bowie])
    await db_session.flush()

    # Create recordings for Bohemian Rhapsody
    bohemian_studio = Recording(
        work_id=bohemian.id,
        title="Bohemian Rhapsody",
        version_type="Studio",
        duration=354.0,
        is_verified=True,
    )
    bohemian_live = Recording(
        work_id=bohemian.id,
        title="Bohemian Rhapsody (Live at Wembley)",
        version_type="Live",
        duration=360.0,
        is_verified=True,
    )
    db_session.add_all([bohemian_studio, bohemian_live])
    await db_session.flush()

    # Create recordings for Under Pressure
    pressure_studio = Recording(
        work_id=pressure.id,
        title="Under Pressure",
        version_type="Studio",
        duration=248.0,
        is_verified=True,
    )
    pressure_unmatched = Recording(
        work_id=pressure.id,
        title="Under Pressure (Remix)",
        version_type="Remix",
        duration=260.0,
        is_verified=False,
    )
    db_session.add_all([pressure_studio, pressure_unmatched])
    await db_session.flush()

    # Add library files (only for some recordings)
    file1 = LibraryFile(
        recording_id=bohemian_studio.id,
        path="/music/queen/bohemian.mp3",
        size=8500000,
        format="mp3",
    )
    file2 = LibraryFile(
        recording_id=pressure_studio.id,
        path="/music/queen/pressure.mp3",
        size=5900000,
        format="mp3",
    )
    db_session.add_all([file1, file2])
    await db_session.commit()

    # ========================================================================
    # Step 1: Get artist detail
    # ========================================================================

    response = await client.get(f"/api/v1/library/artists/{queen.id}")
    assert response.status_code == 200
    artist_data = response.json()

    assert artist_data["id"] == queen.id
    assert artist_data["name"] == "Queen"
    assert artist_data["musicbrainz_id"] == "0383dadf-2a4e-4d10-a46a-e9e041da8eb3"
    assert artist_data["work_count"] == 2
    assert artist_data["recording_count"] == 4

    # ========================================================================
    # Step 2: Get artist's works
    # ========================================================================

    response = await client.get(f"/api/v1/library/artists/{queen.id}/works")
    assert response.status_code == 200
    works_data = response.json()

    assert len(works_data) == 2

    # Find Bohemian Rhapsody
    bohemian_work = next(w for w in works_data if w["title"] == "Bohemian Rhapsody")
    assert bohemian_work["recording_count"] == 2
    assert bohemian_work["duration_total"] == 714.0  # 354 + 360
    assert bohemian_work["artist_names"] == "Queen"

    # Find Under Pressure (multi-artist)
    pressure_work = next(w for w in works_data if w["title"] == "Under Pressure")
    assert pressure_work["recording_count"] == 2
    assert pressure_work["duration_total"] == 508.0  # 248 + 260
    assert "Queen" in pressure_work["artist_names"]
    assert "David Bowie" in pressure_work["artist_names"]

    # ========================================================================
    # Step 3: Get work detail
    # ========================================================================

    response = await client.get(f"/api/v1/library/works/{bohemian.id}")
    assert response.status_code == 200
    work_data = response.json()

    assert work_data["id"] == bohemian.id
    assert work_data["title"] == "Bohemian Rhapsody"
    assert work_data["artist_id"] == queen.id
    assert work_data["artist_name"] == "Queen"
    assert work_data["artist_names"] == "Queen"
    assert work_data["is_instrumental"] is False
    assert work_data["recording_count"] == 2



    # ========================================================================
    # Step 4: Get work's recordings (all)
    # ========================================================================

    response = await client.get(f"/api/v1/library/works/{bohemian.id}/recordings")
    assert response.status_code == 200
    recordings_data = response.json()

    assert len(recordings_data) == 2

    # Verify studio recording
    studio = next(r for r in recordings_data if r["version_type"] == "Studio")
    assert studio["title"] == "Bohemian Rhapsody"
    assert studio["duration"] == 354.0
    assert studio["is_verified"] is True
    assert studio["has_file"] is True

    # Verify live recording
    live = next(r for r in recordings_data if r["version_type"] == "Live")
    assert live["title"] == "Bohemian Rhapsody (Live at Wembley)"
    assert live["duration"] == 360.0
    assert live["is_verified"] is True
    assert live["has_file"] is False

    # ========================================================================
    # Step 5: Test filtering - matched only
    # ========================================================================

    response = await client.get(
        f"/api/v1/library/works/{pressure.id}/recordings",
        params={"status": "matched"}
    )
    assert response.status_code == 200
    matched_data = response.json()

    assert len(matched_data) == 1
    assert matched_data[0]["title"] == "Under Pressure"
    assert matched_data[0]["is_verified"] is True

    # ========================================================================
    # Step 6: Test filtering - unmatched only
    # ========================================================================

    response = await client.get(
        f"/api/v1/library/works/{pressure.id}/recordings",
        params={"status": "unmatched"}
    )
    assert response.status_code == 200
    unmatched_data = response.json()

    assert len(unmatched_data) == 1
    assert unmatched_data[0]["title"] == "Under Pressure (Remix)"
    assert unmatched_data[0]["is_verified"] is False

    # ========================================================================
    # Step 7: Test filtering - library files only
    # ========================================================================

    response = await client.get(
        f"/api/v1/library/works/{pressure.id}/recordings",
        params={"source": "library"}
    )
    assert response.status_code == 200
    library_data = response.json()

    assert len(library_data) == 1
    assert library_data[0]["has_file"] is True

    # ========================================================================
    # Step 8: Test filtering - metadata only
    # ========================================================================

    response = await client.get(
        f"/api/v1/library/works/{pressure.id}/recordings",
        params={"source": "metadata"}
    )
    assert response.status_code == 200
    metadata_data = response.json()

    assert len(metadata_data) == 1
    assert metadata_data[0]["has_file"] is False

    # ========================================================================
    # Step 9: Test pagination
    # ========================================================================

    response = await client.get(
        f"/api/v1/library/works/{bohemian.id}/recordings",
        params={"skip": 0, "limit": 1}
    )
    assert response.status_code == 200
    page1_data = response.json()
    assert len(page1_data) == 1

    response = await client.get(
        f"/api/v1/library/works/{bohemian.id}/recordings",
        params={"skip": 1, "limit": 1}
    )
    assert response.status_code == 200
    page2_data = response.json()
    assert len(page2_data) == 1

    # Ensure different recordings on each page
    assert page1_data[0]["id"] != page2_data[0]["id"]


@pytest.mark.asyncio
async def test_library_navigation_edge_cases(client, db_session):
    """Test edge cases and error handling in library navigation."""

    # ========================================================================
    # Test 1: Non-existent artist
    # ========================================================================

    response = await client.get("/api/v1/library/artists/99999")
    assert response.status_code == 404

    # ========================================================================
    # Test 2: Non-existent work
    # ========================================================================

    response = await client.get("/api/v1/library/works/99999")
    assert response.status_code == 404

    # ========================================================================
    # Test 3: Artist with no works
    # ========================================================================

    artist = Artist(name="Empty Artist")
    db_session.add(artist)
    await db_session.commit()

    response = await client.get(f"/api/v1/library/artists/{artist.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["work_count"] == 0
    assert data["recording_count"] == 0

    response = await client.get(f"/api/v1/library/artists/{artist.id}/works")
    assert response.status_code == 200
    assert response.json() == []

    # ========================================================================
    # Test 4: Work with no recordings
    # ========================================================================

    work = Work(title="Empty Work", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()

    wa = WorkArtist(work_id=work.id, artist_id=artist.id)
    db_session.add(wa)
    await db_session.commit()

    response = await client.get(f"/api/v1/library/works/{work.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["recording_count"] == 0

    response = await client.get(f"/api/v1/library/works/{work.id}/recordings")
    assert response.status_code == 200
    assert response.json() == []
