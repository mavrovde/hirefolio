import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Mavrov.de API" in data["message"]


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_lifespan():
    """Test lifespan startup event."""
    from app.main import app, lifespan

    # We can invoke the lifespan context manager directly
    async with lifespan(app):
        pass  # Just enter and exit to trigger the code
