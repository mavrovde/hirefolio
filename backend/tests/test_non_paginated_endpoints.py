import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_similar_posts_nonexistent_slug(client: AsyncClient):
    """Test similar posts for non-existent slug."""
    response = await client.get("/api/posts/nonexistent-slug-12345/similar")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_similar_posts_no_embedding(client: AsyncClient, db_session):
    """Test similar posts when source post has no embedding."""
    from app.models.post import Post

    # Post without embedding
    db_session.add(
        Post(
            title="Test Post",
            slug="test-post",
            content="Content",
            language="en",
            published=True,
            embedding=None,
        )
    )
    await db_session.commit()

    response = await client.get("/api/posts/test-post/similar")
    assert response.status_code == 200
    assert response.json() == []  # Empty when no embedding


@pytest.mark.asyncio
async def test_similar_posts_only_one_post(client: AsyncClient, db_session):
    """Test similar posts when only one post exists in database."""
    from app.models.post import Post

    db_session.add(
        Post(
            title="Only Post",
            slug="only-post",
            content="Content",
            language="en",
            published=True,
            embedding=[0.1] * 768,  # Dummy embedding
        )
    )
    await db_session.commit()

    response = await client.get("/api/posts/only-post/similar")
    assert response.status_code == 200
    assert response.json() == []  # No other posts to compare


@pytest.mark.asyncio
async def test_similar_posts_limit_zero(client: AsyncClient, db_session):
    """Test similar posts with limit=0."""
    from app.models.post import Post

    db_session.add(
        Post(
            title="Test",
            slug="test",
            content="C",
            language="en",
            published=True,
            embedding=[0.1] * 768,
        )
    )
    await db_session.commit()

    response = await client.get("/api/posts/test/similar?limit=0")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_similar_posts_slug_with_special_chars(client: AsyncClient, db_session):
    """Test similar posts with slug containing special characters."""
    from app.models.post import Post

    db_session.add(
        Post(
            title="Test",
            slug="test-post-2024",
            content="C",
            language="en",
            published=True,
            embedding=[0.1] * 768,
        )
    )
    await db_session.commit()

    response = await client.get("/api/posts/test-post-2024/similar")
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_semantic_search_missing_query(client: AsyncClient):
    """Test semantic search without query parameter."""
    response = await client.get("/api/posts/search/semantic")
    assert response.status_code == 422  # Missing required param


@pytest.mark.asyncio
async def test_semantic_search_very_long_query(client: AsyncClient):
    """Test semantic search with very long query (1000+ chars)."""
    long_query = "a" * 1000
    response = await client.get(f"/api/posts/search/semantic?q={long_query}")
    # Should handle gracefully
    assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio
async def test_semantic_search_special_characters(client: AsyncClient):
    """Test semantic search with special characters in query."""
    queries = [
        "test & search",
        "c++ programming",
        "react/vue.js",
        "test@example.com",
        "100% coverage",
    ]

    for q in queries:
        response = await client.get(f"/api/posts/search/semantic?q={q}")
        # Should not crash
        assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio
async def test_semantic_search_unicode_query(client: AsyncClient):
    """Test semantic search with unicode/emoji in query."""
    queries = [
        "Привет мир",
        "日本語プログラミング",
        "python 🐍 programming",
        "中文搜索",
    ]

    for q in queries:
        response = await client.get(f"/api/posts/search/semantic?q={q}")
        assert response.status_code in [200, 400]


@pytest.mark.asyncio
async def test_semantic_search_invalid_lang(client: AsyncClient):
    """Test semantic search with invalid language code."""
    response = await client.get("/api/posts/search/semantic?q=test&lang=invalid")
    # Should handle gracefully (either accept or reject)
    assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio
async def test_semantic_search_limit_zero(client: AsyncClient):
    """Test semantic search with limit=0."""
    response = await client.get("/api/posts/search/semantic?q=test&limit=0")
    assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_semantic_search_no_posts_in_db(client: AsyncClient, db_session):
    """Test semantic search when no posts exist."""
    response = await client.get("/api/posts/search/semantic?q=test")
    # Should return empty or handle gracefully
    assert response.status_code in [200, 400]


@pytest.mark.asyncio
async def test_semantic_search_posts_without_embeddings(
    client: AsyncClient, db_session
):
    """Test semantic search when posts have no embeddings."""
    from app.models.post import Post

    # Posts without embeddings
    for i in range(3):
        db_session.add(
            Post(
                title=f"Post {i}",
                slug=f"post-{i}",
                content="Content",
                language="en",
                published=True,
                embedding=None,
            )
        )
    await db_session.commit()

    response = await client.get("/api/posts/search/semantic?q=test")
    assert response.status_code in [200, 400]


@pytest.mark.asyncio
async def test_semantic_search_sql_injection_attempt(client: AsyncClient):
    """Test semantic search is safe from SQL injection."""
    malicious_queries = [
        "test' OR '1'='1",
        "test'; DROP TABLE posts; --",
        'test" OR "1"="1',
    ]

    for q in malicious_queries:
        response = await client.get(f"/api/posts/search/semantic?q={q}")
        # Should not crash or expose errors
        assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio
async def test_semantic_search_concurrent_requests(client: AsyncClient):
    """Test multiple concurrent semantic search requests."""
    import asyncio

    queries = ["test1", "test2", "test3", "test4", "test5"]
    tasks = [client.get(f"/api/posts/search/semantic?q={q}") for q in queries]

    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # All should complete (either success or handled error)
    for resp in responses:
        if isinstance(resp, Exception):
            # Connection errors are ok
            continue
        assert resp.status_code in [200, 400, 422]


@pytest.mark.asyncio
async def test_similar_posts_unpublished_excluded(client: AsyncClient, db_session):
    """Test that unpublished posts are excluded from similar results."""
    from app.models.post import Post

    posts = [
        Post(
            title="Published",
            slug="pub",
            content="C",
            language="en",
            published=True,
            embedding=[0.1] * 768,
        ),
        Post(
            title="Draft 1",
            slug="draft1",
            content="C",
            language="en",
            published=False,
            embedding=[0.1] * 768,
        ),
        Post(
            title="Draft 2",
            slug="draft2",
            content="C",
            language="en",
            published=False,
            embedding=[0.1] * 768,
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    response = await client.get("/api/posts/pub/similar")
    assert response.status_code == 200
    data = response.json()
    # Should not include drafts
    for item in data:
        assert item["slug"] not in ["draft1", "draft2"]


@pytest.mark.asyncio
async def test_semantic_search_unpublished_excluded(client: AsyncClient, db_session):
    """Test that semantic search only returns published posts."""
    from app.models.post import Post

    posts = [
        Post(
            title="Published Post",
            slug="pub",
            content="test content",
            language="en",
            published=True,
            embedding=[0.1] * 768,
        ),
        Post(
            title="Draft Post",
            slug="draft",
            content="test content",
            language="en",
            published=False,
            embedding=[0.1] * 768,
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    response = await client.get("/api/posts/search/semantic?q=test")
    if response.status_code == 200:
        data = response.json()
        # Should only have published
        for item in data:
            assert item["slug"] != "draft"
