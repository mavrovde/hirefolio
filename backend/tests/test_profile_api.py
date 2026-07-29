"""Tests for the public GET /profile endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.config import settings
from app.models.profile_snapshot import ProfileSnapshot

URL = f"{settings.api_prefix}/profile"


async def _seed(db, *, version, language, data, is_active):
    row = ProfileSnapshot(
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


async def test_public_get_needs_no_auth(clean_client: AsyncClient, db_session):
    """The public profile endpoint is reachable without any session."""
    await _seed(
        db_session, version="v1", language="en", data={"name": "Public"}, is_active=True
    )
    r = await clean_client.get(URL, params={"lang": "en"})
    assert r.status_code == 200
    assert r.json()["name"] == "Public"


async def test_get_strips_non_public_pii(client: AsyncClient, db_session):
    """A raw scraper JSON with PII must NOT leak it on the public endpoint."""
    await _seed(
        db_session,
        version="v1",
        language="en",
        data={
            "name": "Sergii",
            "headline": "Engineer",
            "experience": [{"title": "Dev"}],
            # Non-public fields a LinkedIn export may carry:
            "phone": "+49 123 456",
            "birthday": "1990-01-01",
            "address": "Secret St 1",
            "connections": ["a", "b"],
            "contactInfo": {"phone": "x"},
        },
        is_active=True,
    )
    body = (await client.get(URL, params={"lang": "en"})).json()
    assert body["name"] == "Sergii"
    assert body["experience"] == [{"title": "Dev"}]
    for leaked in ("phone", "birthday", "address", "connections", "contactInfo"):
        assert leaked not in body


async def test_get_projects_contact_to_email_and_linkedin(
    client: AsyncClient, db_session
):
    """`contact` is exposed but reduced to email + linkedin only."""
    await _seed(
        db_session,
        version="v1",
        language="en",
        data={
            "name": "S",
            "contact": {
                "email": "me@example.com",
                "linkedin": "https://linkedin.com/in/me",
                "phone": "+49 000",
                "address": "private",
            },
        },
        is_active=True,
    )
    contact = (await client.get(URL, params={"lang": "en"})).json()["contact"]
    assert contact == {
        "email": "me@example.com",
        "linkedin": "https://linkedin.com/in/me",
    }


async def test_get_active_profile_rate_limited_after_limit(
    client: AsyncClient, db_session, monkeypatch
):
    """The Nth request within the window returns 429; requests under the limit
    (a normal single request, or several within it) still return 200."""
    from app.api import profile as profile_module

    monkeypatch.setattr(profile_module.profile_rate_limiter, "max_requests", 3)
    await _seed(
        db_session,
        version="v1",
        language="en",
        data={"name": "RateLimited"},
        is_active=True,
    )

    for _ in range(3):
        r = await client.get(URL, params={"lang": "en"})
        assert r.status_code == 200

    r = await client.get(URL, params={"lang": "en"})
    assert r.status_code == 429
    assert "Too many requests" in r.json()["detail"]


async def test_get_active_profile_single_request_not_rate_limited(
    client: AsyncClient, db_session
):
    """A normal single request is never affected by the (generous) rate limit."""
    await _seed(
        db_session, version="v1", language="en", data={"name": "Normal"}, is_active=True
    )
    r = await client.get(URL, params={"lang": "en"})
    assert r.status_code == 200


async def test_get_returns_503_during_schema_warmup(client: AsyncClient, db_session):
    """Startup race (#124): a missing table yields a graceful, retryable 503,
    NOT a raw 500 UndefinedTableError."""
    await db_session.execute(text("DROP TABLE profile_snapshots"))
    await db_session.commit()

    r = await client.get(URL, params={"lang": "en"})
    assert r.status_code == 503
    assert "starting up" in r.json()["detail"]


async def test_get_reraises_non_undefined_table_db_error(client: AsyncClient):
    """A DB ProgrammingError that is NOT a missing table must not be masked as
    503 — it propagates (real error), so we never hide genuine failures."""
    from app.database import get_db
    from app.main import app

    class _FakeUndefinedColumn(Exception):
        sqlstate = "42703"  # undefined_column, not undefined_table

    class _RaisingSession:
        async def execute(self, *args, **kwargs):
            raise ProgrammingError("SELECT 1", {}, _FakeUndefinedColumn())

    async def _override():
        yield _RaisingSession()

    app.dependency_overrides[get_db] = _override
    with pytest.raises(ProgrammingError):
        await client.get(URL, params={"lang": "en"})


async def test_get_handles_non_dict_stored_data(client: AsyncClient, db_session):
    """Defensive: a non-object stored payload projects to an empty object."""
    await _seed(
        db_session,
        version="v1",
        language="en",
        data=["not", "a", "dict"],
        is_active=True,
    )
    r = await client.get(URL, params={"lang": "en"})
    assert r.status_code == 200
    assert r.json() == {}
