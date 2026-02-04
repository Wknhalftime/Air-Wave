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
