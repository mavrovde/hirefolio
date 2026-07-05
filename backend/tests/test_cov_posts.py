"""Coverage-focused tests for app.api.posts.

The post-``await`` lines of the async endpoint handlers are not tracked by
coverage when the handlers run inside the ASGI/greenlet request context, so
these tests call the endpoint coroutines directly (awaited in the test's own
task) while still asserting real behaviour against a live Postgres session.
"""

import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from app.api import posts as posts_api
from app.models.post import Post
from app.models.user import User


def _admin_user():
    return User(
        id=1,
        username="admin",
        email="admin@example.com",
        hashed_password="x",
        is_admin=True,
        is_active=True,
        gemini_api_key=None,
    )


async def _make_post(db_session, **kwargs):
    defaults = dict(
        title="Title",
        slug="slug",
        content="Content body",
        summary="A summary",
        language="en",
        published=True,
        tags=["tag"],
        embedding=[0.1] * 768,
    )
    defaults.update(kwargs)
    post = Post(**defaults)
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)
    return post


@pytest.mark.asyncio
async def test_list_posts_full_response(db_session):
    """count/sort/pagination + response building (156-180)."""
    for i in range(3):
        await _make_post(
            db_session, title=f"Listed {i}", slug=f"listed-{i}", summary=f"s{i}"
        )

    resp = await posts_api.list_posts(
        published_only=True,
        lang=None,
        tag=None,
        page=1,
        page_size=2,
        sort_by="title",
        sort_order="asc",
        search=None,
        db=db_session,
        current_user=None,
    )
    assert resp.total == 3
    assert resp.page_size == 2
    assert resp.total_pages == 2
    assert len(resp.items) == 2
    assert resp.items[0].title == "Listed 0"


@pytest.mark.asyncio
async def test_list_posts_invalid_sort_and_search(db_session):
    """Invalid sort field fallback (166-167) + search filter (146-149)."""
    await _make_post(db_session, slug="needle", title="Unique Needle")
    await _make_post(db_session, slug="other", title="Something Else")

    resp = await posts_api.list_posts(
        published_only=True,
        lang="en",
        tag=None,
        page=1,
        page_size=10,
        sort_by="not_a_column",
        sort_order="desc",
        search="Needle",
        db=db_session,
        current_user=None,
    )
    assert resp.total == 1
    assert resp.items[0].slug == "needle"


@pytest.mark.asyncio
async def test_list_posts_desc_sort(db_session):
    """Descending sort branch (162)."""
    for i in range(2):
        await _make_post(db_session, title=f"Desc {i}", slug=f"desc-{i}")

    resp = await posts_api.list_posts(
        published_only=True,
        lang=None,
        tag=None,
        page=1,
        page_size=10,
        sort_by="title",
        sort_order="desc",
        search=None,
        db=db_session,
        current_user=None,
    )
    assert resp.total == 2
    assert resp.items[0].title == "Desc 1"
    assert resp.items[1].title == "Desc 0"


@pytest.mark.asyncio
async def test_get_post_by_id_found(db_session):
    """get_post_by_id found path + response (210-220)."""
    post = await _make_post(db_session, slug="by-id", title="ById")
    resp = await posts_api.get_post_by_id(id=post.id, db=db_session, current_user=None)
    assert resp.id == post.id
    assert resp.title == "ById"


@pytest.mark.asyncio
async def test_get_post_by_id_draft_hidden_from_anon(db_session):
    """Draft hidden from anonymous user -> 404 (217-218)."""
    post = await _make_post(db_session, slug="draft-hidden-id", published=False)
    with pytest.raises(HTTPException) as exc:
        await posts_api.get_post_by_id(id=post.id, db=db_session, current_user=None)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_post_by_id_draft_admin(db_session):
    """Admin sees draft by id (216-217 branch not raising)."""
    post = await _make_post(db_session, slug="draft-id", published=False)
    resp = await posts_api.get_post_by_id(
        id=post.id, db=db_session, current_user=_admin_user()
    )
    assert resp.published is False


@pytest.mark.asyncio
async def test_get_post_by_id_not_found(db_session):
    with pytest.raises(HTTPException) as exc:
        await posts_api.get_post_by_id(id=999999, db=db_session, current_user=None)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_post_by_slug_found(db_session):
    """get_post by slug found path + response (349-359)."""
    await _make_post(db_session, slug="slug-found", title="BySlug")
    resp = await posts_api.get_post(slug="slug-found", db=db_session, current_user=None)
    assert resp.slug == "slug-found"
    assert resp.title == "BySlug"


@pytest.mark.asyncio
async def test_get_post_by_slug_draft_admin(db_session):
    """Admin sees draft by slug (355-356 branch not raising)."""
    await _make_post(db_session, slug="draft-slug", published=False)
    resp = await posts_api.get_post(
        slug="draft-slug", db=db_session, current_user=_admin_user()
    )
    assert resp.published is False


@pytest.mark.asyncio
async def test_get_post_by_slug_draft_hidden_from_anon(db_session):
    """Draft hidden from anonymous user by slug -> 404 (356-357)."""
    await _make_post(db_session, slug="draft-hidden-slug", published=False)
    with pytest.raises(HTTPException) as exc:
        await posts_api.get_post(
            slug="draft-hidden-slug", db=db_session, current_user=None
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_post_by_slug_not_found(db_session):
    with pytest.raises(HTTPException) as exc:
        await posts_api.get_post(slug="nope", db=db_session, current_user=None)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_semantic_search_merges_vector_and_keyword(db_session):
    """Vector results + keyword merge/boost (273, 298-316)."""
    await _make_post(
        db_session,
        slug="hybrid",
        title="Hybrid Semantic Query",
        content="mentions semantic content",
        summary="semantic summary",
    )
    results = await posts_api.semantic_search(
        q="semantic", lang="en", limit=10, min_relevance=0.3, db=db_session
    )
    assert len(results) == 1
    assert results[0]["slug"] == "hybrid"
    # Found in both vector (mock 0.5) and keyword -> boosted above 0.5.
    assert results[0]["relevance"] > 0.5


@pytest.mark.asyncio
async def test_semantic_search_filters_low_relevance_vector(db_session):
    """Vector result below min_relevance is skipped (298-299 continue)."""
    await _make_post(
        db_session,
        slug="lowrel",
        title="Alpha Beta",
        content="Gamma Delta",
        summary="Epsilon",
    )
    results = await posts_api.semantic_search(
        q="zzzznomatch", lang="en", limit=10, min_relevance=0.9, db=db_session
    )
    # Vector relevance 0.5 < 0.9 threshold -> skipped; keyword misses too.
    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_keyword_only_no_lang(db_session):
    """Keyword-only add with lang falsy (280->283 false branch, 314-316)."""
    await _make_post(
        db_session, slug="keyword-only", title="Keyworditis Special", content="body"
    )
    results = await posts_api.semantic_search(
        q="Keyworditis", lang="", limit=10, min_relevance=0.99, db=db_session
    )
    assert len(results) == 1
    assert results[0]["slug"] == "keyword-only"
    # Keyword-only base score.
    assert abs(results[0]["relevance"] - 0.85) < 1e-6


@pytest.mark.asyncio
async def test_similar_posts_found(db_session):
    """get_similar_posts found + query execute + response (438-463)."""
    await _make_post(db_session, slug="source", title="Source", language="en")
    await _make_post(db_session, slug="neighbor", title="Neighbor", language="en")
    results = await posts_api.get_similar_posts(slug="source", limit=5, db=db_session)
    assert len(results) == 1
    assert results[0].slug == "neighbor"
    # similarity = 1 - mock_distance(0.5)
    assert abs(results[0].similarity - 0.5) < 1e-6


@pytest.mark.asyncio
async def test_similar_posts_no_embedding(db_session):
    """Post without embedding returns empty list (443-444)."""
    await _make_post(db_session, slug="no-embed", embedding=None)
    results = await posts_api.get_similar_posts(slug="no-embed", limit=5, db=db_session)
    assert results == []


@pytest.mark.asyncio
async def test_similar_posts_not_found(db_session):
    with pytest.raises(HTTPException) as exc:
        await posts_api.get_similar_posts(slug="nope", limit=5, db=db_session)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_post_by_id_all_fields(db_session):
    """update_post_by_id all field branches + embedding + response (602-633)."""
    post = await _make_post(
        db_session,
        slug="update-all",
        title="Old",
        content="old",
        summary="old",
        image_url="http://old/img.png",
        language="en",
        published=False,
        tags=["a"],
    )
    update = posts_api.PostUpdate(
        title="New Title",
        content="new content",
        summary="new summary",
        image_url="http://new/img.png",
        language="de",
        published=True,
        tags=["x", "y"],
    )
    resp = await posts_api.update_post_by_id(
        id=post.id, post_data=update, db=db_session, current_user=_admin_user()
    )
    assert resp.title == "New Title"
    assert resp.content == "new content"
    assert resp.summary == "new summary"
    assert resp.image_url == "http://new/img.png"
    assert resp.language == "de"
    assert resp.published is True
    assert resp.tags == ["x", "y"]


@pytest.mark.asyncio
async def test_update_post_by_id_no_fields(db_session):
    """All-None update takes every field skip branch (608->611 ... 626->630)."""
    post = await _make_post(
        db_session, slug="update-none", title="Keep", content="keep"
    )
    resp = await posts_api.update_post_by_id(
        id=post.id,
        post_data=posts_api.PostUpdate(),
        db=db_session,
        current_user=_admin_user(),
    )
    # Nothing changed and no embedding regeneration path taken.
    assert resp.title == "Keep"
    assert resp.content == "keep"


@pytest.mark.asyncio
async def test_update_post_by_id_not_found(db_session):
    with pytest.raises(HTTPException) as exc:
        await posts_api.update_post_by_id(
            id=999999,
            post_data=posts_api.PostUpdate(title="x"),
            db=db_session,
            current_user=_admin_user(),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_post_by_id_found(db_session):
    """delete_post_by_id found path (656-664)."""
    post = await _make_post(db_session, slug="to-delete")
    resp = await posts_api.delete_post_by_id(
        id=post.id, db=db_session, current_user=_admin_user()
    )
    assert resp == {"message": "Post deleted"}


@pytest.mark.asyncio
async def test_delete_post_by_id_not_found(db_session):
    with pytest.raises(HTTPException) as exc:
        await posts_api.delete_post_by_id(
            id=999999, db=db_session, current_user=_admin_user()
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_upload_post_image(db_session):
    """upload_post_image found path + blob storage + response (678-695)."""
    post = await _make_post(db_session, slug="img-upload", image_url="http://old/x.png")
    raw = b"\x89PNG\r\n\x1a\n binarydata"
    upload = UploadFile(
        filename="pic.png",
        file=io.BytesIO(raw),
        headers=Headers({"content-type": "image/png"}),
    )
    resp = await posts_api.upload_post_image(
        post_id=post.id, file=upload, db=db_session, current_user=_admin_user()
    )
    assert resp.id == post.id
    # External URL cleared; display url now resolves to the served blob route.
    assert resp.image_url != "http://old/x.png"

    stored = await db_session.get(Post, post.id)
    assert stored.image_type == "image/png"
    assert stored.image_url is None


@pytest.mark.asyncio
async def test_upload_post_image_not_found(db_session):
    upload = UploadFile(
        filename="pic.png",
        file=io.BytesIO(b"data"),
        headers=Headers({"content-type": "image/png"}),
    )
    with pytest.raises(HTTPException) as exc:
        await posts_api.upload_post_image(
            post_id=999999, file=upload, db=db_session, current_user=_admin_user()
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_post_image_found(db_session):
    """get_post_image streams stored blob (724-732)."""
    post = await _make_post(db_session, slug="img-get")
    post.image_blob = b"rawimagebytes"
    post.image_type = "image/jpeg"
    db_session.add(post)
    await db_session.commit()

    resp = await posts_api.get_post_image(post_id=post.id, db=db_session)
    assert resp.media_type == "image/jpeg"
    body = b"".join([chunk async for chunk in resp.body_iterator])
    assert body == b"rawimagebytes"


@pytest.mark.asyncio
async def test_get_post_image_not_found(db_session):
    """Post without a blob yields 404 (726-727)."""
    post = await _make_post(db_session, slug="img-none")
    with pytest.raises(HTTPException) as exc:
        await posts_api.get_post_image(post_id=post.id, db=db_session)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_generate_post_slug_collision_retry(db_session, mocker):
    """generate_post retry path succeeds on slug collision (561-576)."""
    await _make_post(db_session, slug="collide-slug", title="Existing")

    async def fake_generate(*args, **kwargs):
        return {
            "title": "Generated",
            "content": "Generated content",
            "slug": "collide-slug",
            "summary": "gen summary",
            "tags": ["g"],
        }

    mocker.patch("app.services.ai.generate_full_post", side_effect=fake_generate)

    request = posts_api.PostGenerationRequest(topic="T", keywords=["k"], language="en")
    resp = await posts_api.generate_post_endpoint(
        request=request, db=db_session, current_user=_admin_user()
    )
    assert resp.title == "Generated"
    # Slug regenerated with a random suffix due to the unique collision.
    assert resp.slug.startswith("collide-slug-")
    assert resp.slug != "collide-slug"
