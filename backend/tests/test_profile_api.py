"""Tests for the public GET /profile endpoint."""

from httpx import AsyncClient

from app.config import settings
from app.models.profile_version import ProfileVersion

URL = f"{settings.api_prefix}/profile"


async def _seed(db, *, version, language, data, is_active):
    row = ProfileVersion(
        version=version, language=language, data=data, is_active=is_active
    )
    db.add(row)
    await db.commit()
    return row


async def test_get_active_profile_returns_data(client: AsyncClient, db_session):
    await _seed(
        db_session,
        version="v1",
        language="en",
        data={"name": "Sergii", "headline": "Engineer"},
        is_active=True,
    )
    r = await client.get(URL, params={"lang": "en"})
    assert r.status_code == 200
    assert r.json() == {"name": "Sergii", "headline": "Engineer"}


async def test_get_defaults_to_english(client: AsyncClient, db_session):
    await _seed(
        db_session, version="v1", language="en", data={"name": "EN"}, is_active=True
    )
    r = await client.get(URL)  # no lang param
    assert r.status_code == 200
    assert r.json()["name"] == "EN"


async def test_get_is_language_specific(client: AsyncClient, db_session):
    await _seed(
        db_session, version="v1", language="en", data={"name": "EN"}, is_active=True
    )
    await _seed(
        db_session, version="v1", language="de", data={"name": "DE"}, is_active=True
    )
    assert (await client.get(URL, params={"lang": "de"})).json()["name"] == "DE"
    assert (await client.get(URL, params={"lang": "en"})).json()["name"] == "EN"


async def test_get_ignores_inactive_versions(client: AsyncClient, db_session):
    await _seed(
        db_session, version="v1", language="en", data={"name": "old"}, is_active=False
    )
    r = await client.get(URL, params={"lang": "en"})
    assert r.status_code == 404


async def test_get_no_active_profile_is_404(client: AsyncClient):
    r = await client.get(URL, params={"lang": "en"})
    assert r.status_code == 404
    assert "No active profile" in r.json()["detail"]


async def test_get_unsupported_language_is_400(client: AsyncClient):
    r = await client.get(URL, params={"lang": "fr"})
    assert r.status_code == 400
    assert "Unsupported language" in r.json()["detail"]
