import re
from datetime import UTC

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


@pytest.mark.asyncio
async def test_public_stats_uptime_without_start_time(client: AsyncClient):
    """Test that /stats/public returns Unknown when start_time is not set."""
    from app.main import app

    # Temporarily remove start_time if it exists
    original = None
    if hasattr(app.state, "start_time"):
        original = app.state.start_time
        delattr(app.state, "start_time")

    try:
        response = await client.get(f"{settings.api_prefix}/stats/public")
        assert response.status_code == 200
        assert response.json()["uptime"] == "Unknown"
    finally:
        if original is not None:
            app.state.start_time = original


@pytest.mark.asyncio
async def test_public_stats_uptime_with_start_time(client: AsyncClient):
    """Test that /stats/public returns uptime when start_time is set."""
    from datetime import datetime

    from app.main import app

    # Temporarily set start_time
    original = getattr(app.state, "start_time", None)
    app.state.start_time = datetime.now(UTC)

    try:
        response = await client.get(f"{settings.api_prefix}/stats/public")
        assert response.status_code == 200
        data = response.json()
        assert data["uptime"] != "Unknown"
        assert "start_time" in data
    finally:
        if original is not None:
            app.state.start_time = original
        else:
            delattr(app.state, "start_time")
