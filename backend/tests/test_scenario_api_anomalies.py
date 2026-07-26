from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import settings
from app.main import app
from app.services.auth import get_current_user_optional

# Note: The 'client' fixture in conftest.py sets a global override making requests Admin by default.
# We need to overwrite app.dependency_overrides inside specific tests to simulate Anon or User.


@pytest.mark.asyncio
async def test_list_posts_include_drafts(client: AsyncClient, mock_embedding):
    """Test listing posts including drafts as admin."""
    # Default is admin, so we can create draft
    post_data = {
        "title": "Draft",
        "slug": "draft-1",
        "content": "Secret",
        "published": False,
    }

    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        await client.post(f"{settings.api_prefix}/posts", json=post_data)

    # Request as admin (default override) with published_only=false
    response = await client.get(f"{settings.api_prefix}/posts?published_only=false")

    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert any(p["slug"] == "draft-1" for p in items)


@pytest.mark.asyncio
async def test_get_draft_post_as_anon(client: AsyncClient, mock_embedding):
    # 1. Create draft (as admin, default fixture)
    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        create_res = await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Draft",
                "slug": "secret",
                "content": "x",
                "published": False,
            },
        )
        assert create_res.status_code == 200

    # 2. Switch to Anon
    app.dependency_overrides[get_current_user_optional] = lambda: None

    # 3. Try to get as anon
    try:
        response = await client.get(f"{settings.api_prefix}/posts/secret")
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
    finally:
        # Restore fixture's admin mock (optional if client fixture tears down, but good practice)
        pass  # tearing down is handled by fixture potentially, but we modified the dict object reference.
        # Actually client fixture clears overrides at end. So we are fine.


@pytest.mark.asyncio
async def test_update_post_not_found(client: AsyncClient):
    response = await client.put(
        f"{settings.api_prefix}/posts/999999", json={"title": "New"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_post_partial(client: AsyncClient, mock_embedding):
    # Create post
    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        create_resp = await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Old",
                "slug": "partial",
                "content": "Old",
                "published": True,
            },
        )
        post_id = create_resp.json()["id"]

    # Update only title
    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        response = await client.put(
            f"{settings.api_prefix}/posts/{post_id}", json={"title": "New"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New"
    assert data["content"] == "Old"


@pytest.mark.asyncio
async def test_delete_post_not_found(client: AsyncClient):
    response = await client.delete(f"{settings.api_prefix}/posts/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_similar_posts_not_found(client: AsyncClient):
    response = await client.get(f"{settings.api_prefix}/posts/ghost/similar")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_similar_posts_no_embedding(client: AsyncClient, mock_embedding):
    # Create valid post
    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "NoEmb",
                "slug": "no-emb",
                "content": "x",
                "published": True,
            },
        )

    # We cannot easily create a post with NULL embedding via API validation.
    # But we can update it if we mock the update logic? No, update regenerates it.
    # We would need to manually update DB.
    # Since client fixture mocks DB session via override_get_db yielding 'db_session',
    # we can try to access that session fixture here if we passed it.


@pytest.mark.asyncio
async def test_semantic_search_with_results(client: AsyncClient, mock_embedding):
    # Create post
    # Patch where it is imported in app.api.posts
    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "SearchMe",
                "slug": "search-me",
                "content": "This content contains the query string.",
                "published": True,
            },
        )

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.get(
            f"{settings.api_prefix}/posts/search/semantic?q=query"
        )

    assert response.status_code == 200
    assert len(response.json()) > 0


@pytest.mark.asyncio
async def test_semantic_search_no_language_filter(client: AsyncClient, mock_embedding):
    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.get(
            f"{settings.api_prefix}/posts/search/semantic?q=query&lang="
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_post_too_many_tags(client: AsyncClient, mock_embedding):
    """Test creating a post with more than 5 tags."""
    tags = [f"tag{i}" for i in range(6)]
    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        response = await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Too Many Tags",
                "slug": "too-many-tags",
                "content": "Content",
                "tags": tags,
                "published": True,
            },
        )
    assert response.status_code == 422
    # Detailed check might depend on Pydantic version/format
    assert "Max 5 tags allowed" in response.text


@pytest.mark.asyncio
async def test_update_post_too_many_tags(client: AsyncClient, mock_embedding):
    """Test updating a post with more than 5 tags."""
    # Create valid post
    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        create_res = await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Valid Tags",
                "slug": "valid-tags",
                "content": "Content",
                "tags": ["tag1"],
                "published": True,
            },
        )
    post_id = create_res.json()["id"]

    # Update with too many tags
    tags = [f"tag{i}" for i in range(6)]
    response = await client.put(
        f"{settings.api_prefix}/posts/{post_id}", json={"tags": tags}
    )
    assert response.status_code == 422
    assert "Max 5 tags allowed" in response.text


@pytest.mark.asyncio
async def test_semantic_search_embedding_unavailable(client: AsyncClient):
    """Test semantic search when embedding service fails (returns None)."""
    with patch("app.api.posts.get_embedding", return_value=None):
        response = await client.get(
            f"{settings.api_prefix}/posts/search/semantic?q=query"
        )

    assert response.status_code == 200
    # Should return empty list (or keyword results if any match)
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_similar_posts_missing_embedding(
    client: AsyncClient, mock_embedding, db_session
):
    """Test get_similar_posts when the source post has no embedding."""
    from app.models.post import Post

    # Create post with embedding
    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "NoEmbSource",
                "slug": "no-emb-source",
                "content": "x",
                "published": True,
            },
        )

    # Manually clear embedding in DB
    from sqlalchemy import select

    res = await db_session.execute(select(Post).where(Post.slug == "no-emb-source"))
    post = res.scalar_one()
    post.embedding = None
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/posts/no-emb-source/similar")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_posts_drafts_as_anon_force_published(
    client: AsyncClient, mock_embedding
):
    """Test that non-admins are forced to published_only=true."""
    # 1. Create draft (as admin)
    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Draft",
                "slug": "d1",
                "content": "x",
                "published": False,
            },
        )

    # 2. Switch to Anon
    app.dependency_overrides[get_current_user_optional] = lambda: None

    # 3. Request drafts
    try:
        response = await client.get(f"{settings.api_prefix}/posts?published_only=false")
        assert response.status_code == 200
        data = response.json()
        items = data["items"]
        assert not any(p["slug"] == "d1" for p in items)
    finally:
        pass


@pytest.mark.asyncio
async def test_get_draft_post_by_id_as_anon(client: AsyncClient, mock_embedding):
    """Test retrieving a draft post by ID as anon results in 404."""
    # 1. Create draft (as admin)
    with patch("app.services.embeddings.get_embedding", return_value=mock_embedding):
        create_res = await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Draft",
                "slug": "d1-id",
                "content": "x",
                "published": False,
            },
        )
    post_id = create_res.json()["id"]

    # 2. Switch to Anon
    app.dependency_overrides[get_current_user_optional] = lambda: None

    # 3. Try to get by ID
    response = await client.get(f"{settings.api_prefix}/posts/{post_id}")
    assert response.status_code == 404
