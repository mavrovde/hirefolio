"""Tests for POST /api/app/linkedin/import-posts-json (bulk scraper upload)
and its image-download / URL-pick helpers.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.linkedin import _download_image_best_effort, _pick_image_url
from app.config import settings
from app.models.post import Post

URL = f"{settings.api_prefix}/linkedin/import-posts-json"
TOKEN = "test-import-token"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.fixture(autouse=True)
def _set_token(monkeypatch):
    monkeypatch.setattr(settings, "linkedin_import_token", TOKEN)


def _hdr(token=TOKEN):
    return {"X-Import-Token": token} if token is not None else {}


def _file(payload, name="posts.json"):
    if isinstance(payload, (list, dict)):
        payload = json.dumps(payload).encode()
    elif isinstance(payload, str):
        payload = payload.encode()
    return {"file": (name, payload, "application/json")}


async def _get(db: AsyncSession, urn: str) -> Post:
    return (await db.execute(select(Post).where(Post.source_urn == urn))).scalar_one()


# --- endpoint: auth ---------------------------------------------------------


async def test_missing_token_is_401(clean_client: AsyncClient):
    r = await clean_client.post(URL, files=_file([]), headers={})
    assert r.status_code == 401


async def test_admin_session_authorizes(client: AsyncClient):
    # `client` fixture is an admin session — no token needed.
    with patch(
        "app.api.linkedin._download_image_best_effort",
        new=AsyncMock(return_value=(None, None)),
    ):
        r = await client.post(
            URL, files=_file([{"urn": "urn:1", "content": "Hello world"}])
        )
    assert r.status_code == 200


# --- endpoint: payload validation ------------------------------------------


async def test_invalid_json_is_400(clean_client: AsyncClient):
    r = await clean_client.post(URL, files=_file(b"{bad"), headers=_hdr())
    assert r.status_code == 400
    assert "not valid JSON" in r.json()["detail"]


async def test_non_array_is_400(clean_client: AsyncClient):
    r = await clean_client.post(URL, files=_file({"not": "array"}), headers=_hdr())
    assert r.status_code == 400
    assert "top-level array" in r.json()["detail"]


# --- endpoint: import behavior ---------------------------------------------


async def test_creates_drafts_and_is_idempotent(
    clean_client: AsyncClient, db_session: AsyncSession
):
    entries = [
        {
            "urn": "urn:li:activity:1",
            "content": "First post about #angular and AI",
            "language": "de",
            "postedAt": "2026-07-23T22:14:00Z",
            "url": "https://linkedin.com/p/1",
        }
    ]
    with patch(
        "app.api.linkedin._download_image_best_effort",
        new=AsyncMock(return_value=(None, None)),
    ):
        r1 = await clean_client.post(URL, files=_file(entries), headers=_hdr())
        assert r1.json() == {"created": 1, "updated": 0, "skipped": 0, "count": 1}

        post = await _get(db_session, "urn:li:activity:1")
        assert post.published is False  # draft
        assert post.language == "de"
        assert post.source_url == "https://linkedin.com/p/1"
        assert post.posted_at is not None

        # Re-upload the same URN → update, not duplicate.
        r2 = await clean_client.post(URL, files=_file(entries), headers=_hdr())
        assert r2.json()["updated"] == 1 and r2.json()["created"] == 0

    all_posts = (
        await db_session.execute(
            select(Post).where(Post.source_urn == "urn:li:activity:1")
        )
    ).scalars().all()
    assert len(all_posts) == 1


async def test_skips_entries_without_urn_or_content(clean_client: AsyncClient):
    entries = [
        {"urn": "", "content": "no urn"},
        {"urn": "urn:2", "content": "   "},  # blank content after normalize
        "not-a-dict",
        {"urn": "urn:3", "content": "valid post body here"},
    ]
    with patch(
        "app.api.linkedin._download_image_best_effort",
        new=AsyncMock(return_value=(None, None)),
    ):
        r = await clean_client.post(URL, files=_file(entries), headers=_hdr())
    body = r.json()
    assert body == {"created": 1, "updated": 0, "skipped": 3, "count": 4}


async def test_downloaded_image_is_stored_locally(
    clean_client: AsyncClient, db_session: AsyncSession
):
    entries = [{"urn": "urn:img", "content": "post with image", "imageUrl": "http://x/i.png"}]
    with patch(
        "app.api.linkedin._download_image_best_effort",
        new=AsyncMock(return_value=(PNG, "image/png")),
    ):
        r = await clean_client.post(URL, files=_file(entries), headers=_hdr())
    assert r.status_code == 200
    post = await _get(db_session, "urn:img")
    assert post.image_type == "image/png"
    assert post.image_url is None  # served locally, not hotlinked


async def test_failed_image_download_keeps_remote_url(
    clean_client: AsyncClient, db_session: AsyncSession
):
    entries = [
        {"urn": "urn:fallback", "content": "post img fallback", "imageUrls": ["http://x/f.jpg"]}
    ]
    with patch(
        "app.api.linkedin._download_image_best_effort",
        new=AsyncMock(return_value=(None, None)),
    ):
        r = await clean_client.post(URL, files=_file(entries), headers=_hdr())
    assert r.status_code == 200
    post = await _get(db_session, "urn:fallback")
    assert post.image_url == "http://x/f.jpg"  # remote URL kept as fallback


# --- helper: _pick_image_url ------------------------------------------------


def test_pick_image_url_prefers_single():
    assert _pick_image_url({"imageUrl": "a", "imageUrls": ["b"]}) == "a"


def test_pick_image_url_falls_back_to_list():
    assert _pick_image_url({"imageUrl": None, "imageUrls": ["b", "c"]}) == "b"


def test_pick_image_url_none_when_absent():
    assert _pick_image_url({"imageUrls": []}) is None


# --- helper: _download_image_best_effort ------------------------------------


async def test_download_none_url_returns_none():
    assert await _download_image_best_effort(None) == (None, None)


@respx.mock
async def test_download_success_with_cookie(monkeypatch):
    monkeypatch.setattr(settings, "linkedin_cookie_li_at", "cookie123")
    respx.get("http://img/ok.png").mock(
        return_value=Response(200, content=PNG, headers={"content-type": "image/png"})
    )
    data, ctype = await _download_image_best_effort("http://img/ok.png")
    assert data == PNG and ctype == "image/png"


@respx.mock
async def test_download_wrong_content_type_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "linkedin_cookie_li_at", "")
    respx.get("http://img/x.html").mock(
        return_value=Response(200, content=b"<html>", headers={"content-type": "text/html"})
    )
    assert await _download_image_best_effort("http://img/x.html") == (None, None)


@respx.mock
async def test_download_too_large_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "linkedin_cookie_li_at", "c")
    monkeypatch.setattr(settings, "import_max_image_mb", 0)  # any bytes exceed 0 MB
    respx.get("http://img/big.png").mock(
        return_value=Response(200, content=PNG, headers={"content-type": "image/png"})
    )
    assert await _download_image_best_effort("http://img/big.png") == (None, None)


@respx.mock
async def test_download_network_error_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "linkedin_cookie_li_at", "c")
    respx.get("http://img/err.png").mock(return_value=Response(500))
    assert await _download_image_best_effort("http://img/err.png") == (None, None)
