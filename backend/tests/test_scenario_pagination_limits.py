import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_posts_invalid_page_zero(client: AsyncClient, db_session):
    """Test that page=0 is handled (should default to 1)."""
    from app.models.post import Post

    db_session.add(
        Post(title="Test", slug="test", content="Test", language="en", published=True)
    )
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/posts?page=0")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_posts_invalid_page_negative(client: AsyncClient):
    """Test that negative page numbers are rejected."""
    response = await client.get(f"{settings.api_prefix}/posts?page=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_posts_page_size_exceeds_max(client: AsyncClient):
    """Test that page_size > 100 is rejected."""
    response = await client.get(f"{settings.api_prefix}/posts?page_size=101")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_posts_page_size_zero(client: AsyncClient):
    """Test that page_size=0 is rejected."""
    response = await client.get(f"{settings.api_prefix}/posts?page_size=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_posts_invalid_sort_order(client: AsyncClient):
    """Test that invalid sort_order is rejected."""
    response = await client.get(f"{settings.api_prefix}/posts?sort_order=invalid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_posts_empty_search_string(client: AsyncClient, db_session):
    """Test that empty search string returns all results."""
    from app.models.post import Post

    posts = [
        Post(
            title="Test 1",
            slug="test-1",
            content="Content",
            language="en",
            published=True,
        ),
        Post(
            title="Test 2",
            slug="test-2",
            content="Content",
            language="en",
            published=True,
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/posts?search=")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # Empty search returns all


@pytest.mark.asyncio
async def test_posts_search_sql_injection_attempt(client: AsyncClient, db_session):
    """Test that SQL injection attempts are safely handled."""
    from app.models.post import Post

    db_session.add(
        Post(
            title="Test", slug="test", content="Content", language="en", published=True
        )
    )
    await db_session.commit()

    # Try SQL injection
    response = await client.get(f"{settings.api_prefix}/posts?search=' OR '1'='1")
    assert response.status_code == 200
    data = response.json()
    # Should not return all results, should be treated as literal string
    assert data["total"] == 0  # No match for this literal string


@pytest.mark.asyncio
async def test_posts_unicode_search(client: AsyncClient, db_session):
    """Test search with unicode characters."""
    from app.models.post import Post

    posts = [
        Post(
            title="Привет мир",
            slug="privet",
            content="Content",
            language="ru",
            published=True,
        ),
        Post(
            title="Test Post",
            slug="test",
            content="Content",
            language="en",
            published=True,
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/posts?search=Привет")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "Привет" in data["items"][0]["title"]


@pytest.mark.asyncio
async def test_posts_exact_page_boundary(client: AsyncClient, db_session):
    """Test pagination at exact page boundaries."""
    from app.models.post import Post

    # Create exactly 20 posts (2 full pages of 10)
    for i in range(20):
        db_session.add(
            Post(
                title=f"Post {i}",
                slug=f"post-{i}",
                content="Content",
                language="en",
                published=True,
            )
        )
    await db_session.commit()

    # Page 1 should have 10
    response = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 20
    assert len(data["items"]) == 10
    assert data["total_pages"] == 2

    # Page 2 should have exactly 10
    response = await client.get(f"{settings.api_prefix}/posts?page=2&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10

    # Page 3 should be empty
    response = await client.get(f"{settings.api_prefix}/posts?page=3&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_posts_single_item_multiple_pages(client: AsyncClient, db_session):
    """Test pagination with page_size=1."""
    from app.models.post import Post

    for i in range(3):
        db_session.add(
            Post(
                title=f"Post {i}",
                slug=f"post-{i}",
                content="Content",
                language="en",
                published=True,
            )
        )
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1
    assert data["total_pages"] == 3


@pytest.mark.asyncio
async def test_posts_sort_with_null_values(client: AsyncClient, db_session):
    """Test sorting when some records have null values."""
    from app.models.post import Post

    # Posts with and without summaries
    posts = [
        Post(
            title="A",
            slug="a",
            content="Content",
            summary="Summary A",
            language="en",
            published=True,
        ),
        Post(
            title="B",
            slug="b",
            content="Content",
            summary=None,
            language="en",
            published=True,
        ),
        Post(
            title="C",
            slug="c",
            content="Content",
            summary="Summary C",
            language="en",
            published=True,
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    response = await client.get(
        f"{settings.api_prefix}/posts?sort_by=summary&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_cv_requests_search_empty_fields(client: AsyncClient, db_session):
    """Test CV search when some fields are empty."""
    from app.models.cv_request import CvRequest

    requests = [
        CvRequest(name="John", email="john@test.com", company="", message="Test"),
        CvRequest(
            name="Jane", email="jane@test.com", company="ACME Corp", message="Test"
        ),
    ]
    for req in requests:
        db_session.add(req)
    await db_session.commit()

    # Search should work even with empty company
    response = await client.get(f"{settings.api_prefix}/admin/cv/requests?search=john")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_tags_search_with_hyphen(client: AsyncClient, db_session):
    """Test tag search with hyphens."""
    from app.models.post import Post

    posts = [
        Post(
            title="Post 1",
            slug="p1",
            content="C",
            language="en",
            published=True,
            tags=["next-js", "react"],
        ),
        Post(
            title="Post 2",
            slug="p2",
            content="C",
            language="en",
            published=True,
            tags=["vue-js"],
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/tags?search=next-js")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_tags_duplicate_tags_counted_once(client: AsyncClient, db_session):
    """Test that duplicate tags are counted correctly."""
    from app.models.post import Post

    # Same tag in multiple posts
    posts = [
        Post(
            title="P1",
            slug="p1",
            content="C",
            language="en",
            published=True,
            tags=["python", "backend"],
        ),
        Post(
            title="P2",
            slug="p2",
            content="C",
            language="en",
            published=True,
            tags=["python", "ai"],
        ),
        Post(
            title="P3",
            slug="p3",
            content="C",
            language="en",
            published=True,
            tags=["python"],
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/tags")
    assert response.status_code == 200
    data = response.json()

    # Find python tag
    python_tag = next((t for t in data["items"] if t["name"] == "python"), None)
    assert python_tag is not None
    assert python_tag["count"] == 3
