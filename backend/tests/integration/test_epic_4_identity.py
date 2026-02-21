import pytest
from httpx import AsyncClient
from sqlalchemy import select
from airwave.core.models import IdentityBridge, ArtistAlias, Recording, Work, Artist

@pytest.fixture
async def setup_identity_data(db_session):
    """Setup basic data for identity tests."""
    artist = Artist(name="Test Artist")
    db_session.add(artist)
    await db_session.flush()
    
    work = Work(title="Test Song", artist_id=artist.id)
    db_session.add(work)
    await db_session.flush()
    
    recording = Recording(work_id=work.id, title="Test Song", version_type="Original")
    db_session.add(recording)
    await db_session.commit()
    return recording

@pytest.mark.asyncio
async def test_list_bridges(async_client: AsyncClient, db_session, setup_identity_data):
    """Test GET /identity/bridges returns all bridges."""
    recording = setup_identity_data
    
    # Create Bridge (links to work)
    bridge = IdentityBridge(
        log_signature="test_sig_list",
        reference_artist="Raw Artist",
        reference_title="Raw Title",
        work_id=recording.work_id
    )
    db_session.add(bridge)
    await db_session.commit()
    
    # Test endpoint
    response = await async_client.get("/api/v1/identity/bridges")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    
    # Verify structure matches schema
    item = next(i for i in data if i["id"] == bridge.id)
    assert item["raw_artist"] == "Raw Artist"
    assert item["recording"]["artist"] == "Test Artist"

@pytest.mark.asyncio
async def test_delete_bridge(async_client: AsyncClient, db_session, setup_identity_data):
    """Test DELETE /identity/bridges/{id} soft-deletes (revokes) bridge."""
    recording = setup_identity_data
    bridge = IdentityBridge(
        log_signature="test_sig_del",
        reference_artist="To Delete",
        reference_title="Title",
        work_id=recording.work_id
    )
    db_session.add(bridge)
    await db_session.commit()
    
    response = await async_client.delete(f"/api/v1/identity/bridges/{bridge.id}")
    assert response.status_code == 200
    
    # API soft-deletes (sets is_revoked=True); same session so bridge is updated
    assert bridge.is_revoked is True

@pytest.mark.asyncio
async def test_create_bridge(async_client: AsyncClient, db_session, setup_identity_data):
    """Test POST /identity/bridges creates new bridge."""
    recording = setup_identity_data
    
    payload = {
        "raw_artist": "New Artist",
        "raw_title": "New Song",
        "recording_id": recording.id
    }
    
    response = await async_client.post("/api/v1/identity/bridges", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    
    # Verify creation
    stmt = select(IdentityBridge).where(
        IdentityBridge.reference_artist == "New Artist"
    )
    result = await db_session.execute(stmt)
    bridge = result.scalar_one_or_none()
    assert bridge is not None
    assert bridge.log_signature is not None

@pytest.mark.asyncio
async def test_create_alias(async_client: AsyncClient, db_session):
    """Test POST /identity/aliases creates alias."""
    payload = {
        "raw_name": "The Beatles",
        "resolved_name": "Beatles"
    }
    response = await async_client.post("/api/v1/identity/aliases", json=payload)
    assert response.status_code == 200
    
    # Verify creation
    stmt = select(ArtistAlias).where(ArtistAlias.raw_name == "The Beatles")
    result = await db_session.execute(stmt)
    alias = result.scalar_one_or_none()
    assert alias is not None
    assert alias.resolved_name == "Beatles"

@pytest.mark.asyncio
async def test_delete_alias(async_client: AsyncClient, db_session):
    """Test DELETE /identity/aliases/{id} removes alias."""
    alias = ArtistAlias(raw_name="Test Del", resolved_name="Resolved", is_verified=True)
    db_session.add(alias)
    await db_session.commit()
    
    response = await async_client.delete(f"/api/v1/identity/aliases/{alias.id}")
    assert response.status_code == 200
    
    # Verify deletion
    stmt = select(ArtistAlias).where(ArtistAlias.id == alias.id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None
