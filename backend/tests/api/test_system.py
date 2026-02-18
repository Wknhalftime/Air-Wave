import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Verify health endpoint."""
    response = await client.get("/api/v1/system/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_config(client: AsyncClient):
    """Verify config endpoint."""
    response = await client.get("/api/v1/system/config")

    assert response.status_code == 200
    data = response.json()
    assert "log_level" in data


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    """Verify root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Airwave" in data["message"]


@pytest.mark.asyncio
async def test_get_cache_stats(client: AsyncClient):
    """Verify cache stats endpoint."""
    response = await client.get("/api/v1/system/cache/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["cache_enabled"] is True
    assert "total_entries" in data
    assert "active_entries" in data
    assert "expired_entries" in data


@pytest.mark.asyncio
async def test_clear_cache(client: AsyncClient):
    """Verify cache clear endpoint."""
    response = await client.post("/api/v1/system/cache/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "message" in data
