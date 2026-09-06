"""Tests for the admin profile endpoints (upload / versions / activate).

Covers multilanguage isolation (EN and DE each keep their own active version),
validation (bad JSON, non-object, empty version, bad language, duplicate), the
paginated version listing, activation, and the error/500 paths.
"""

import json
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.profile_snapshot import ProfileSnapshot

UPLOAD = f"{settings.api_prefix}/admin/profile/upload"
VERSIONS = f"{settings.api_prefix}/admin/profile/versions"


def _file(payload, name="profile.json", content_type="application/json"):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload).encode()
    elif isinstance(payload, str):
        payload = payload.encode()
    return {"file": (name, payload, content_type)}


async def _rows(db: AsyncSession, language=None):
    q = select(ProfileSnapshot)
    if language:
        q = q.where(ProfileSnapshot.language == language)
    return (await db.execute(q)).scalars().all()


# --- upload -----------------------------------------------------------------


async def test_upload_success_makes_active(client: AsyncClient, db_session):
    r = await client.post(
        UPLOAD,
        files=_file({"name": "Testa", "experience": []}),
        data={"version": "v1", "language": "en"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {"success": True, "version": "v1", "language": "en"}

    rows = await _rows(db_session, "en")
    assert len(rows) == 1
    assert rows[0].is_active is True
    assert rows[0].data["name"] == "Testa"


async def test_upload_second_version_switches_active(client: AsyncClient, db_session):
    await client.post(
        UPLOAD, files=_file({"name": "A"}), data={"version": "v1", "language": "en"}
    )
    await client.post(
        UPLOAD, files=_file({"name": "B"}), data={"version": "v2", "language": "en"}
    )
    rows = {r.version: r.is_active for r in await _rows(db_session, "en")}
    assert rows == {"v1": False, "v2": True}


async def test_upload_is_multilanguage_isolated(client: AsyncClient, db_session):
    """EN and DE each keep their own active version simultaneously."""
    await client.post(
        UPLOAD, files=_file({"name": "EN"}), data={"version": "v1", "language": "en"}
    )
    await client.post(
        UPLOAD, files=_file({"name": "DE"}), data={"version": "v1", "language": "de"}
    )
    en = await _rows(db_session, "en")
    de = await _rows(db_session, "de")
    assert len(en) == 1 and en[0].is_active is True
    assert len(de) == 1 and de[0].is_active is True


async def test_upload_invalid_json_is_400(client: AsyncClient):
    r = await client.post(
        UPLOAD, files=_file(b"{not json"), data={"version": "v1", "language": "en"}
    )
    assert r.status_code == 400
    assert "not valid JSON" in r.json()["detail"]


async def test_upload_non_object_json_is_400(client: AsyncClient):
    r = await client.post(
        UPLOAD, files=_file([1, 2, 3]), data={"version": "v1", "language": "en"}
    )
    assert r.status_code == 400
    assert "top-level object" in r.json()["detail"]


async def test_upload_empty_version_is_400(client: AsyncClient):
    r = await client.post(
        UPLOAD, files=_file({"name": "X"}), data={"version": "   ", "language": "en"}
    )
    assert r.status_code == 400
    assert "must not be empty" in r.json()["detail"]


async def test_upload_bad_language_is_400(client: AsyncClient):
    r = await client.post(
        UPLOAD, files=_file({"name": "X"}), data={"version": "v1", "language": "fr"}
    )
    assert r.status_code == 400
    assert "Unsupported language" in r.json()["detail"]


async def test_upload_duplicate_version_language_is_409(client: AsyncClient):
    await client.post(
        UPLOAD, files=_file({"name": "X"}), data={"version": "v1", "language": "en"}
    )
    r = await client.post(
        UPLOAD, files=_file({"name": "Y"}), data={"version": "v1", "language": "en"}
    )
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


async def test_upload_db_error_is_500(client: AsyncClient):
    # Fail inside the try block (after the duplicate-check select) to hit the
    # rollback/500 path — patch the `update` used for the deactivate step.
    with patch("app.api.admin_profile.update", side_effect=RuntimeError("boom")):
        r = await client.post(
            UPLOAD,
            files=_file({"name": "X"}),
            data={"version": "v9", "language": "en"},
        )
    assert r.status_code == 500
    assert "Failed to upload profile" in r.json()["detail"]


# --- versions listing -------------------------------------------------------


async def test_versions_list_omits_data(client: AsyncClient):
    await client.post(
        UPLOAD, files=_file({"name": "X"}), data={"version": "v1", "language": "en"}
    )
    r = await client.get(VERSIONS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert set(item) == {"id", "version", "language", "is_active", "created_at"}
    assert "data" not in item


async def test_versions_pagination(client: AsyncClient):
    for i in range(3):
        await client.post(
            UPLOAD,
            files=_file({"n": i}),
            data={"version": f"v{i}", "language": "en"},
        )
    r = await client.get(VERSIONS, params={"page": 1, "page_size": 2})
    body = r.json()
    assert body["total"] == 3
    assert body["total_pages"] == 2
    assert len(body["items"]) == 2


async def test_versions_language_filter(client: AsyncClient):
    await client.post(
        UPLOAD, files=_file({"n": 1}), data={"version": "v1", "language": "en"}
    )
    await client.post(
        UPLOAD, files=_file({"n": 2}), data={"version": "v1", "language": "de"}
    )
    r = await client.get(VERSIONS, params={"language": "de"})
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["language"] == "de"


async def test_versions_sort_asc_and_unknown_field_fallback(client: AsyncClient):
    await client.post(
        UPLOAD, files=_file({"n": 1}), data={"version": "v1", "language": "en"}
    )
    # asc branch
    r_asc = await client.get(VERSIONS, params={"sort_order": "asc"})
    assert r_asc.status_code == 200
    # unknown sort_by → falls back to created_at desc branch
    r_bad = await client.get(VERSIONS, params={"sort_by": "does_not_exist"})
    assert r_bad.status_code == 200


async def test_versions_empty(client: AsyncClient):
    r = await client.get(VERSIONS)
    body = r.json()
    assert body["total"] == 0
    assert body["total_pages"] == 1
    assert body["items"] == []


async def test_versions_sort_by_class_attr_is_safe(client: AsyncClient):
    """A non-orderable class attribute (e.g. 'metadata') must not 500 — the
    sort_by allowlist falls back to created_at instead of reaching order_by."""
    await client.post(
        UPLOAD, files=_file({"n": 1}), data={"version": "v1", "language": "en"}
    )
    r = await client.get(VERSIONS, params={"sort_by": "metadata"})
    assert r.status_code == 200


async def test_versions_sort_by_allowlisted_column(client: AsyncClient):
    await client.post(
        UPLOAD, files=_file({"n": 1}), data={"version": "v1", "language": "en"}
    )
    r = await client.get(VERSIONS, params={"sort_by": "version", "sort_order": "asc"})
    assert r.status_code == 200


async def test_upload_oversized_is_413(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.api.admin_profile.MAX_PROFILE_JSON_BYTES", 10)
    r = await client.post(
        UPLOAD,
        files=_file({"name": "x" * 50}),
        data={"version": "v1", "language": "en"},
    )
    assert r.status_code == 413
    assert "exceeds" in r.json()["detail"]


# --- activate ---------------------------------------------------------------


async def test_activate_switches_active(client: AsyncClient, db_session):
    await client.post(
        UPLOAD, files=_file({"n": 1}), data={"version": "v1", "language": "en"}
    )
    await client.post(
        UPLOAD, files=_file({"n": 2}), data={"version": "v2", "language": "en"}
    )
    v1 = next(r for r in await _rows(db_session, "en") if r.version == "v1")

    r = await client.patch(f"{VERSIONS}/{v1.id}/activate")
    assert r.status_code == 200
    assert r.json()["version"] == "v1"

    db_session.expire_all()
    active = {r.version: r.is_active for r in await _rows(db_session, "en")}
    assert active == {"v1": True, "v2": False}


async def test_activate_unknown_id_is_404(client: AsyncClient):
    r = await client.patch(f"{VERSIONS}/00000000-0000-0000-0000-000000000000/activate")
    assert r.status_code == 404


async def test_activate_db_error_is_500(client: AsyncClient, db_session):
    await client.post(
        UPLOAD, files=_file({"n": 1}), data={"version": "v1", "language": "en"}
    )
    row = (await _rows(db_session, "en"))[0]
    with patch("app.api.admin_profile.update", side_effect=RuntimeError("boom")):
        r = await client.patch(f"{VERSIONS}/{row.id}/activate")
    assert r.status_code == 500
    assert "Failed to activate" in r.json()["detail"]


# --- authentication / authorization matrix ---------------------------------

_DUMMY_ID = "00000000-0000-0000-0000-000000000000"


async def test_upload_requires_auth(clean_client: AsyncClient):
    """No session → 401 (never reaches the handler)."""
    r = await clean_client.post(
        UPLOAD, files=_file({"n": 1}), data={"version": "v1", "language": "en"}
    )
    assert r.status_code == 401


async def test_upload_forbidden_for_non_admin(normal_client: AsyncClient):
    """A logged-in non-admin is forbidden (403)."""
    r = await normal_client.post(
        UPLOAD, files=_file({"n": 1}), data={"version": "v1", "language": "en"}
    )
    assert r.status_code == 403


async def test_versions_requires_auth(clean_client: AsyncClient):
    assert (await clean_client.get(VERSIONS)).status_code == 401


async def test_versions_forbidden_for_non_admin(normal_client: AsyncClient):
    assert (await normal_client.get(VERSIONS)).status_code == 403


async def test_activate_requires_auth(clean_client: AsyncClient):
    r = await clean_client.patch(f"{VERSIONS}/{_DUMMY_ID}/activate")
    assert r.status_code == 401


async def test_activate_forbidden_for_non_admin(normal_client: AsyncClient):
    r = await normal_client.patch(f"{VERSIONS}/{_DUMMY_ID}/activate")
    assert r.status_code == 403
