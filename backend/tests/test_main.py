import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import settings


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert f"{settings.site_name} API" in data["message"]


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Health reports ready (200) once the schema is present."""
    response = await client.get(f"{settings.api_prefix}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["ready"] is True


@pytest.mark.asyncio
async def test_health_not_ready_when_schema_missing(client: AsyncClient, db_session):
    """During the startup race (#124) health reports a retryable 503, not 200."""
    await db_session.execute(text("DROP TABLE profile_snapshots"))
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "initializing"
    assert data["ready"] is False


@pytest.mark.asyncio
async def test_health_not_ready_when_db_unreachable(client: AsyncClient, monkeypatch):
    """A DB error during the probe surfaces as not-ready (503), never a raw 500."""

    async def _boom(_session):
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr("app.main.schema_ready", _boom)

    response = await client.get(f"{settings.api_prefix}/health")
    assert response.status_code == 503
    assert response.json()["ready"] is False


@pytest.mark.asyncio
async def test_ping(client: AsyncClient) -> None:
    """Test ping endpoint."""
    response = await client.get(f"{settings.api_prefix}/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "ok"}


def test_retired_prefix_warning_names_the_keys(monkeypatch, capsys):
    """#330 hard break: a leftover retired-prefix key must be NAMED at startup,
    not silently ignored — the failure mode is 'my token stopped working'."""
    from app.main import RETIRED_ENV_PREFIX, _warn_retired_env

    monkeypatch.setenv(f"{RETIRED_ENV_PREFIX}GEMINI_API_KEY", "x")
    monkeypatch.setenv(f"{RETIRED_ENV_PREFIX}TELEGRAM_CHAT_ID", "y")
    _warn_retired_env()
    out = capsys.readouterr().out
    assert "IGNORED since the #330 rebrand" in out
    assert f"{RETIRED_ENV_PREFIX}GEMINI_API_KEY" in out
    assert f"{RETIRED_ENV_PREFIX}TELEGRAM_CHAT_ID" in out


def test_retired_prefix_warning_silent_when_clean(monkeypatch, capsys):
    import os

    from app.main import RETIRED_ENV_PREFIX, _warn_retired_env

    for k in list(os.environ):
        if k.startswith(RETIRED_ENV_PREFIX):
            monkeypatch.delenv(k)
    _warn_retired_env()
    assert "IGNORED" not in capsys.readouterr().out


def test_retired_prefix_warning_reads_the_forwarded_channel(monkeypatch, capsys):
    """In a container the retired keys never reach the process env; compose
    forwards their NAMES via LEGACY_GEMINI_ENV — the diagnostic must read it."""
    from app.main import RETIRED_ENV_PREFIX, _warn_retired_env

    monkeypatch.setenv(
        "LEGACY_GEMINI_ENV", f"GEMINI_API_KEY {RETIRED_ENV_PREFIX}TELEGRAM_BOT_TOKEN"
    )
    _warn_retired_env()
    out = capsys.readouterr().out
    assert f"{RETIRED_ENV_PREFIX}TELEGRAM_BOT_TOKEN" in out
    assert "GEMINI_API_KEY," not in out  # pre-#141 names belong to the other warning
