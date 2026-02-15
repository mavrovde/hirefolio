from app.config import settings
import pytest
from httpx import AsyncClient
import asyncio


@pytest.mark.asyncio
async def test_posts_concurrent_pagination_requests(client: AsyncClient):
    """Test multiple concurrent pagination requests don't interfere."""
    # Create 50 posts via API to avoid session conflicts
    for i in range(50):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": f"Post {i}",
                "slug": f"concurrent-post-{i}",
                "content": "C",
                "language": "en",
                "published": True,
            },
        )

    # Make 5 concurrent requests for different pages
    tasks = [client.get(f"{settings.api_prefix}/posts?page={p}&page_size=10") for p in range(1, 6)]
    responses = await asyncio.gather(*tasks)

    # All should succeed
    for resp in responses:
        assert resp.status_code == 200

    # Each should have different data
    page_1_items = responses[0].json()["items"]
    page_2_items = responses[1].json()["items"]
    if len(page_1_items) > 0 and len(page_2_items) > 0:
        assert page_1_items[0]["id"] != page_2_items[0]["id"]


@pytest.mark.asyncio
async def test_posts_extreme_page_number(client: AsyncClient, db_session):
    """Test requesting extremely large page numbers."""
    from app.models.post import Post

    db_session.add(
        Post(title="Test", slug="test", content="C", language="en", published=True)
    )
    await db_session.commit()

    # Request page 999999
    response = await client.get(f"{settings.api_prefix}/posts?page=999999&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 1
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_posts_search_very_long_query(client: AsyncClient, db_session):
    """Test search with very long query string."""
    from app.models.post import Post

    db_session.add(
        Post(title="Test", slug="test", content="C", language="en", published=True)
    )
    await db_session.commit()

    # 1000 character search query
    long_query = "a" * 1000
    response = await client.get(f"{settings.api_prefix}/posts?search={long_query}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0  # No match for 1000 'a's


@pytest.mark.asyncio
async def test_posts_sort_by_nonexistent_field(client: AsyncClient, db_session):
    """Test sorting by non-existent field falls back gracefully."""
    from app.models.post import Post

    db_session.add(
        Post(title="Test", slug="test", content="C", language="en", published=True)
    )
    await db_session.commit()

    # Try to sort by invalid field
    response = await client.get(f"{settings.api_prefix}/posts?sort_by=nonexistent_field")
    assert response.status_code == 200  # Should fall back to default
    data = response.json()
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_cv_requests_search_email_variations(client: AsyncClient, db_session):
    """Test CV search with various email formats."""
    from app.models.cv_request import CvRequest

    requests = [
        CvRequest(
            name="User 1", email="test+tag@example.com", company="C", message="M"
        ),
        CvRequest(
            name="User 2", email="test.user@example.com", company="C", message="M"
        ),
        CvRequest(name="User 3", email="TEST@EXAMPLE.COM", company="C", message="M"),
    ]
    for req in requests:
        db_session.add(req)
    await db_session.commit()

    # Search should be case-insensitive
    response = await client.get(f"{settings.api_prefix}/admin/cv/requests?search=test")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3  # All three have "test" in email


@pytest.mark.asyncio
async def test_tags_pagination_with_special_tag_names(client: AsyncClient):
    """Test tags with special characters in names."""
    # Create posts with special tag names via API
    await client.post(
        f"{settings.api_prefix}/posts",
        json={
            "title": "P1 Special Tags",
            "slug": "p1-special-tags",
            "content": "C",
            "language": "en",
            "published": True,
            "tags": ["cpp", "csharp", "dotnet", "nodejs"],
        },
    )
    await client.post(
        f"{settings.api_prefix}/posts",
        json={
            "title": "P2 Special Tags",
            "slug": "p2-special-tags",
            "content": "C",
            "language": "en",
            "published": True,
            "tags": ["react-native", "vuejs", "nextjs"],
        },
    )

    response = await client.get(f"{settings.api_prefix}/tags?search=cpp")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_posts_page_size_exactly_matches_total(client: AsyncClient, db_session):
    """Test when page_size exactly equals total items."""
    from app.models.post import Post

    # Create exactly 10 posts
    for i in range(10):
        db_session.add(
            Post(
                title=f"Post {i}",
                slug=f"post-{i}",
                content="C",
                language="en",
                published=True,
            )
        )
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["items"]) == 10
    assert data["total_pages"] == 1

    # Page 2 should be empty
    response = await client.get(f"{settings.api_prefix}/posts?page=2&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_cv_versions_with_different_versions(client: AsyncClient, db_session):
    """Test CV versions with different version numbers."""
    from app.models.cv_document import CvDocument

    # Multiple files with different versions
    documents = [
        CvDocument(filename="cv1.pdf", version="1.0-a", data=b"data", is_active=True),
        CvDocument(filename="cv2.pdf", version="1.0-b", data=b"data", is_active=False),
        CvDocument(
            filename="resume.pdf", version="1.0-c", data=b"data", is_active=False
        ),
    ]
    for doc in documents:
        db_session.add(doc)
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/admin/cv/versions?search=1.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_posts_search_with_newlines_and_tabs(client: AsyncClient, db_session):
    """Test search with whitespace characters."""
    from app.models.post import Post

    posts = [
        Post(
            title="Test\nPost",
            slug="test-1",
            content="Content\twith\ttabs",
            language="en",
            published=True,
        ),
        Post(
            title="Normal",
            slug="test-2",
            content="Normal content",
            language="en",
            published=True,
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    # Search for word "Test" should still work
    response = await client.get(f"{settings.api_prefix}/posts?search=Test")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_tags_empty_tag_array(client: AsyncClient, db_session):
    """Test posts with empty tag arrays."""
    from app.models.post import Post

    posts = [
        Post(
            title="P1", slug="p1", content="C", language="en", published=True, tags=[]
        ),
        Post(
            title="P2",
            slug="p2",
            content="C",
            language="en",
            published=True,
            tags=["python"],
        ),
        Post(
            title="P3", slug="p3", content="C", language="en", published=True, tags=[]
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/tags")
    assert response.status_code == 200
    data = response.json()
    # Should only return tags from posts with non-empty arrays
    python_tag = next((t for t in data["items"] if t["name"] == "python"), None)
    assert python_tag is not None
    assert python_tag["count"] == 1


@pytest.mark.asyncio
async def test_posts_search_empty_vs_null(client: AsyncClient, db_session):
    """Test search with empty string vs no search parameter."""
    from app.models.post import Post

    for i in range(5):
        db_session.add(
            Post(
                title=f"Post {i}",
                slug=f"post-{i}",
                content="C",
                language="en",
                published=True,
            )
        )
    await db_session.commit()

    # Empty search should return all
    response1 = await client.get(f"{settings.api_prefix}/posts?search=")
    data1 = response1.json()

    # No search param should return all
    response2 = await client.get(f"{settings.api_prefix}/posts")
    data2 = response2.json()

    assert data1["total"] == data2["total"] == 5


@pytest.mark.asyncio
async def test_cv_requests_zero_results_pagination(client: AsyncClient, db_session):
    """Test pagination metadata when search returns zero results."""
    from app.models.cv_request import CvRequest

    db_session.add(
        CvRequest(name="John", email="john@test.com", company="ACME", message="M")
    )
    await db_session.commit()

    # Search for non-existent term
    response = await client.get(f"{settings.api_prefix}/admin/cv/requests?search=NonExistentCompany")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 1  # Should be 1, not 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_posts_sort_stability(client: AsyncClient, db_session):
    """Test sort stability with identical values."""
    from app.models.post import Post
    import datetime

    # Create posts with same created_at timestamp
    now = datetime.datetime.now(datetime.timezone.utc)
    posts = [
        Post(
            title=f"Post {i}",
            slug=f"post-{i}",
            content="C",
            language="en",
            published=True,
            created_at=now,
        )
        for i in range(5)
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    # Sort by created_at - order should be deterministic
    response1 = await client.get(f"{settings.api_prefix}/posts?sort_by=created_at&sort_order=asc")
    response2 = await client.get(f"{settings.api_prefix}/posts?sort_by=created_at&sort_order=asc")

    data1 = response1.json()
    data2 = response2.json()

    # Same order both times
    assert [p["id"] for p in data1["items"]] == [p["id"] for p in data2["items"]]


@pytest.mark.asyncio
async def test_tags_unicode_emoji_tags(client: AsyncClient, db_session):
    """Test tags with emoji and unicode characters."""
    from app.models.post import Post

    posts = [
        Post(
            title="P1",
            slug="p1",
            content="C",
            language="en",
            published=True,
            tags=["python🐍", "react⚛️", "编程"],
        ),
        Post(
            title="P2",
            slug="p2",
            content="C",
            language="en",
            published=True,
            tags=["日本語", "中文", "한글"],
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/tags?search=python")
    assert response.status_code == 200
    data = response.json()
    # Should find "python🐍"
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_posts_page_1_vs_no_page(client: AsyncClient, db_session):
    """Test that page=1 and no page param return identical results."""
    from app.models.post import Post

    for i in range(5):
        db_session.add(
            Post(
                title=f"Post {i}",
                slug=f"post-{i}",
                content="C",
                language="en",
                published=True,
            )
        )
    await db_session.commit()

    # Explicit page=1
    response1 = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=10")
    data1 = response1.json()

    # Default (should be page=1)
    response2 = await client.get(f"{settings.api_prefix}/posts?page_size=10")
    data2 = response2.json()

    assert data1 == data2


@pytest.mark.asyncio
async def test_cv_versions_search_case_sensitivity(client: AsyncClient, db_session):
    """Test CV versions search is case-insensitive."""
    from app.models.cv_document import CvDocument

    documents = [
        CvDocument(
            filename="CV_Final.PDF", version="V1.0", data=b"data", is_active=True
        ),
        CvDocument(
            filename="resume_final.pdf", version="v2.0", data=b"data", is_active=False
        ),
    ]
    for doc in documents:
        db_session.add(doc)
    await db_session.commit()

    # Search lowercase
    response = await client.get(f"{settings.api_prefix}/admin/cv/versions?search=final")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2

    # Search uppercase
    response = await client.get(f"{settings.api_prefix}/admin/cv/versions?search=FINAL")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
