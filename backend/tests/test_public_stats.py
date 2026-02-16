import re
import pytest
from httpx import AsyncClient
from app.config import settings


@pytest.mark.asyncio
async def test_public_stats_returns_version(client: AsyncClient):
    """Test that /stats/public returns a valid backend_version."""
    response = await client.get(f"{settings.api_prefix}/stats/public")
    assert response.status_code == 200
    data = response.json()
    assert "backend_version" in data
    # Version must be a semver-like string (e.g. "1.1.30")
    assert re.match(r"^\d+\.\d+\.\d+", data["backend_version"]), (
        f"backend_version '{data['backend_version']}' is not a valid semver"
    )


@pytest.mark.asyncio
async def test_public_stats_returns_visitor_ip(client: AsyncClient):
    """Test that /stats/public returns visitor_ip."""
    response = await client.get(f"{settings.api_prefix}/stats/public")
    assert response.status_code == 200
    data = response.json()
    assert "visitor_ip" in data
    assert data["visitor_ip"]  # non-empty


@pytest.mark.asyncio
async def test_public_stats_returns_uptime(client: AsyncClient):
    """Test that /stats/public returns uptime."""
    response = await client.get(f"{settings.api_prefix}/stats/public")
    assert response.status_code == 200
    data = response.json()
    assert "uptime" in data
    assert data["uptime"]  # non-empty
