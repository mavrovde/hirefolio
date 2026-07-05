"""Final coverage tests to reach 100% statement + branch coverage for app.

Grouped by target module. New tests only; no existing tests modified.
"""
import json
import os
import uuid

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock

from tests.fixtures_auth_custom import (  # noqa: F401
    admin_token_headers,
    normal_user_token_headers,
    admin_user,
    normal_user,
)


# ---------------------------------------------------------------------------
# app/api/admin_sql.py
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_sql_non_admin_403(db_session):
    """Line 43: current_user.is_admin False -> 403 (dependency passes but flag off)."""
    from app.main import app
    from app.database import get_db
    from app.services.auth import get_current_admin_user
    from app.models.user import User
    from httpx import ASGITransport

    async def override_get_db():
        yield db_session

    non_admin = User(
        id=99,
        username="notadmin",
        email="notadmin@example.com",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )

    async def override_auth():
        return non_admin

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin_user] = override_auth
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/app/admin/sql/execute", json={"query": "SELECT 1"}
            )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Not authorized"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_sql_row_cap_exceeded(client: AsyncClient):
    """Line 68 + 79: SELECT returning > MAX_ROWS raises 400 (HTTPException re-raise)."""
    resp = await client.post(
        "/api/app/admin/sql/execute",
        json={"query": "SELECT * FROM generate_series(1,501)"},
    )
    assert resp.status_code == 400
    assert "exceeds 500 rows" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_sql_non_select_commit(client: AsyncClient):
    """Lines 74-76: non-SELECT commit path returns success message."""
    resp = await client.post(
        "/api/app/admin/sql/execute",
        json={"query": "UPDATE posts SET title=title WHERE 1=0"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["message"] == "Query executed successfully"
    assert "duration_ms" in data[0]


# ---------------------------------------------------------------------------
# app/api/ai.py  (line 89: multi-chat StreamingResponse)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ai_multi_chat_streaming(client: AsyncClient):
    async def fake_conversation(agents, topic):
        yield json.dumps({"agent": 1, "content": "hi", "done": False}) + "\n"
        yield json.dumps({"agent": 0, "content": "[done]", "done": True}) + "\n"

    with patch(
        "app.api.ai.multi_agent_conversation",
        side_effect=fake_conversation,
    ):
        resp = await client.post(
            "/api/app/ai/multi-chat",
            json={
                "agents": [{"id": 1, "description": "d", "role": "r"}],
                "topic": "T",
            },
        )
        assert resp.status_code == 200
        body = resp.text
        assert "[done]" in body


# ---------------------------------------------------------------------------
# app/api/auth.py  (line 129: GET /auth/me)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auth_me(client: AsyncClient):
    resp = await client.get("/api/app/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["is_admin"] is True


# ---------------------------------------------------------------------------
# app/api/cv.py  (branch 82->92: req_id present but not found in DB)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cv_download_unknown_req_id(client: AsyncClient, db_session):
    """req_id is a valid UUID not in DB -> cv_request is None, still serves active CV."""
    from app.models.cv_document import CvDocument

    doc = CvDocument(
        filename="cv.pdf",
        data=b"%PDF-1.4 test",
        version="1.0",
        is_active=True,
    )
    db_session.add(doc)
    await db_session.commit()

    random_id = str(uuid.uuid4())
    resp = await client.get(f"/api/app/cv/download?req_id={random_id}")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 test"
    assert resp.headers["content-type"] == "application/pdf"


# ---------------------------------------------------------------------------
# app/api/posts.py
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_post_by_id_draft_as_admin(client: AsyncClient, db_session):
    """Branch 211->214: unpublished post fetched by an admin -> returned (no raise)."""
    from app.models.post import Post

    post = Post(
        title="Draft",
        slug="draft-by-id",
        content="secret",
        summary="s",
        language="en",
        published=False,
        tags=[],
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    resp = await client.get(f"/api/app/posts/{post.id}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "draft-by-id"


@pytest.mark.asyncio
async def test_semantic_search_short_query(client: AsyncClient):
    """Line 357: query shorter than 2 chars -> []"""
    resp = await client.get("/api/app/posts/search/semantic?q=a")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_semantic_search_vector_and_keyword(client: AsyncClient, db_session):
    """Lines 378-379, 402-409, 415-416: vector path + min_relevance + keyword boost."""
    from app.models.post import Post

    # Post that matches BOTH vector (has embedding) and keyword (title contains term)
    both = Post(
        title="Python Rocks",
        slug="python-rocks",
        content="all about python programming",
        summary="python summary",
        language="en",
        published=True,
        tags=[],
        embedding=[0.1] * 768,
    )
    # Post with embedding only (vector match, low/varied relevance)
    vec_only = Post(
        title="Unrelated",
        slug="vec-only",
        content="different content here",
        summary="sum",
        language="en",
        published=True,
        tags=[],
        embedding=[0.2] * 768,
    )
    db_session.add_all([both, vec_only])
    await db_session.commit()

    with patch("app.api.posts.get_embedding", new=AsyncMock(return_value=[0.1] * 768)):
        resp = await client.get(
            "/api/app/posts/search/semantic?q=Python&lang=en&limit=10"
        )
    assert resp.status_code == 200
    slugs = [r["slug"] for r in resp.json()]
    assert "python-rocks" in slugs


@pytest.mark.asyncio
async def test_semantic_search_min_relevance_filters_all(client: AsyncClient, db_session):
    """Lines 403-405: min_relevance > 1.0 filters out every vector result."""
    from app.models.post import Post

    p = Post(
        title="Zebra",
        slug="zebra-post",
        content="zzz",
        summary="s",
        language="en",
        published=True,
        tags=[],
        embedding=[0.9] * 768,
    )
    db_session.add(p)
    await db_session.commit()

    with patch("app.api.posts.get_embedding", new=AsyncMock(return_value=[0.1] * 768)):
        resp = await client.get(
            "/api/app/posts/search/semantic?q=nomatchkeyword&lang=en&min_relevance=1.5"
        )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_semantic_search_no_embedding(client: AsyncClient, db_session):
    """Branch 363->385: get_embedding returns None -> vector block skipped, keyword only."""
    from app.models.post import Post

    p = Post(
        title="Keyword Only Post",
        slug="kw-only",
        content="contains searchterm here",
        summary="s",
        language="en",
        published=True,
        tags=[],
    )
    db_session.add(p)
    await db_session.commit()

    with patch("app.api.posts.get_embedding", new=AsyncMock(return_value=None)):
        resp = await client.get("/api/app/posts/search/semantic?q=searchterm&lang=en")
    assert resp.status_code == 200
    slugs = [r["slug"] for r in resp.json()]
    assert "kw-only" in slugs
    # keyword-only base relevance (line 419)
    assert resp.json()[0]["relevance"] == 0.85


@pytest.mark.asyncio
async def test_semantic_search_no_lang(client: AsyncClient, db_session):
    """Branches 372->376 and 387->390: lang omitted (falsy) -> no language filter."""
    from app.models.post import Post

    p = Post(
        title="Global Post about elephants",
        slug="global-post",
        content="elephants roam",
        summary="s",
        language="de",
        published=True,
        tags=[],
        embedding=[0.3] * 768,
    )
    db_session.add(p)
    await db_session.commit()

    with patch("app.api.posts.get_embedding", new=AsyncMock(return_value=[0.3] * 768)):
        resp = await client.get("/api/app/posts/search/semantic?q=elephants&lang=")
    assert resp.status_code == 200
    slugs = [r["slug"] for r in resp.json()]
    assert "global-post" in slugs


@pytest.mark.asyncio
async def test_semantic_search_vector_exception(client: AsyncClient, db_session):
    """Branch 380-382: vector query raises -> fallback to keyword only."""
    from app.models.post import Post

    p = Post(
        title="Fallback Post uniquekw",
        slug="fallback-post",
        content="body",
        summary="s",
        language="en",
        published=True,
        tags=[],
    )
    db_session.add(p)
    await db_session.commit()

    # get_embedding returns a wrong-dimension vector -> DB raises -> except pass
    with patch("app.api.posts.get_embedding", new=AsyncMock(return_value=[0.1] * 5)):
        resp = await client.get("/api/app/posts/search/semantic?q=uniquekw&lang=en")
    assert resp.status_code == 200
    slugs = [r["slug"] for r in resp.json()]
    assert "fallback-post" in slugs


@pytest.mark.asyncio
async def test_generate_post_success(client: AsyncClient):
    """Lines 481-522: successful generation + save."""
    generated = {
        "title": "Gen Title",
        "slug": "gen-slug-unique",
        "content": "# Content",
        "summary": "Gen summary",
        "tags": ["a", "b"],
    }
    with (
        patch(
            "app.services.ai.generate_full_post",
            new=AsyncMock(return_value=generated),
        ),
        patch("app.api.posts.get_embedding", new=AsyncMock(return_value=[0.1] * 768)),
    ):
        resp = await client.post(
            "/api/app/posts/generate",
            json={"topic": "T", "keywords": ["k"], "language": "en"},
        )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "gen-slug-unique"
    assert resp.json()["published"] is False


@pytest.mark.asyncio
async def test_generate_post_none_returns_500(client: AsyncClient):
    """Lines 490-491: generate_full_post returns falsy -> 500."""
    with patch(
        "app.services.ai.generate_full_post", new=AsyncMock(return_value=None)
    ):
        resp = await client.post(
            "/api/app/posts/generate",
            json={"topic": "T", "keywords": [], "language": "en"},
        )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to generate post content"


@pytest.mark.asyncio
async def test_generate_post_slug_retry_fallback(client: AsyncClient, db_session):
    """Lines 523-530: first commit fails on duplicate slug -> retry with random suffix."""
    from app.models.post import Post

    existing = Post(
        title="Existing",
        slug="dup-slug",
        content="c",
        summary="s",
        language="en",
        published=True,
        tags=[],
    )
    db_session.add(existing)
    await db_session.commit()

    generated = {
        "title": "New",
        "slug": "dup-slug",  # collides with existing unique slug
        "content": "C",
        "summary": "S",
        "tags": [],
    }
    with (
        patch(
            "app.services.ai.generate_full_post",
            new=AsyncMock(return_value=generated),
        ),
        patch("app.api.posts.get_embedding", new=AsyncMock(return_value=[0.1] * 768)),
    ):
        resp = await client.post(
            "/api/app/posts/generate",
            json={"topic": "T", "keywords": [], "language": "en"},
        )
    assert resp.status_code == 200
    assert resp.json()["slug"].startswith("dup-slug-")


# ---------------------------------------------------------------------------
# app/api/stats.py (branch 139->149: no start_time on app.state)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_public_stats_without_start_time(client: AsyncClient):
    from app.main import app

    saved = getattr(app.state, "start_time", None)
    if hasattr(app.state, "start_time"):
        delattr(app.state, "start_time")
    try:
        resp = await client.get("/api/app/stats/public")
        assert resp.status_code == 200
        data = resp.json()
        assert data["uptime"] == "Unknown"
        assert data["start_time"] is None
    finally:
        if saved is not None:
            app.state.start_time = saved


# ---------------------------------------------------------------------------
# app/main.py  (line 33: RuntimeError when jwt secret empty & not testing)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lifespan_requires_jwt_secret():
    from app.main import app, lifespan
    from app.config import settings

    saved_secret = settings.jwt_secret_key
    saved_testing = os.environ.get("TESTING")
    settings.jwt_secret_key = ""
    os.environ["TESTING"] = "false"
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            async with lifespan(app):
                pass
    finally:
        settings.jwt_secret_key = saved_secret
        if saved_testing is None:
            os.environ.pop("TESTING", None)
        else:
            os.environ["TESTING"] = saved_testing


# ---------------------------------------------------------------------------
# app/services/chat.py (branches 33->exit, 34->33, 39->42)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_with_llm_line_variants():
    """Empty line (34->33 falsy), empty content (39->42), content line, loop exits (33->exit)."""
    from app.services.chat import chat_with_llm

    lines = [
        "",  # falsy line -> skips (34->33)
        json.dumps({"message": {"content": ""}}),  # empty content (39->42, no yield)
        json.dumps({"message": {"content": "hello"}}),  # content yielded
        # no "done": True anywhere -> loop exits naturally (33->exit)
    ]

    async def fake_aiter_lines():
        for line in lines:
            yield line

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = fake_aiter_lines

    class StreamCM:
        async def __aenter__(self):
            return mock_resp

        async def __aexit__(self, *a):
            pass

    class ClientCM:
        def stream(self, *a, **k):
            return StreamCM()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    with patch("app.services.chat.httpx.AsyncClient", return_value=ClientCM()):
        out = [c async for c in chat_with_llm([{"role": "user", "content": "hi"}])]

    assert out == ["hello"]
