from app.config import settings
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_posts_sort_all_fields(client: AsyncClient, db_session):
    """Test that ALL sortable fields work correctly."""
    from app.models.post import Post
    import datetime

    # Create posts with different dates
    now = datetime.datetime.now(datetime.timezone.utc)
    posts = [
        Post(
            title="Zebra",
            slug="z",
            content="C",
            language="en",
            published=True,
            created_at=now - datetime.timedelta(days=2),
        ),
        Post(
            title="Alpha",
            slug="a",
            content="C",
            language="en",
            published=True,
            created_at=now - datetime.timedelta(days=1),
        ),
        Post(
            title="Beta",
            slug="b",
            content="C",
            language="en",
            published=True,
            created_at=now,
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    # Test sort by title
    response = await client.get(
        f"{settings.api_prefix}/posts?sort_by=title&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["title"] == "Alpha"

    # Test sort by slug
    response = await client.get(
        f"{settings.api_prefix}/posts?sort_by=slug&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["slug"] == "z"

    # Test sort by created_at (newest first)
    response = await client.get(
        f"{settings.api_prefix}/posts?sort_by=created_at&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["title"] == "Beta"


@pytest.mark.asyncio
async def test_cv_requests_sort_all_fields(client: AsyncClient, db_session):
    """Test CV requests sorting by all available fields."""
    from app.models.cv_request import CvRequest
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    requests = [
        CvRequest(
            name="Zebra",
            email="z@test.com",
            company="Z",
            message="M",
            created_at=now - datetime.timedelta(days=1),
            download_count=5,
        ),
        CvRequest(
            name="Alpha",
            email="a@test.com",
            company="A",
            message="M",
            created_at=now,
            download_count=10,
        ),
    ]
    for req in requests:
        db_session.add(req)
    await db_session.commit()

    # Sort by name
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?sort_by=name&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "Alpha"

    # Sort by email
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?sort_by=email&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["email"] == "z@test.com"

    # Sort by download_count
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?sort_by=download_count&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["download_count"] == 10


@pytest.mark.asyncio
async def test_cv_versions_all_sort_fields(client: AsyncClient, db_session):
    """Test CV versions sorting by all fields."""
    from app.models.cv_document import CvDocument

    documents = [
        CvDocument(filename="resume.pdf", version="2.0", data=b"data", is_active=False),
        CvDocument(filename="cv.pdf", version="1.0", data=b"data", is_active=True),
        CvDocument(filename="doc.pdf", version="3.0", data=b"data", is_active=False),
    ]
    for doc in documents:
        db_session.add(doc)
    await db_session.commit()

    # Sort by filename
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/versions?sort_by=filename&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["filename"] == "cv.pdf"

    # Sort by version
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/versions?sort_by=version&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["version"] == "3.0"

    # Sort by is_active
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/versions?sort_by=is_active&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["is_active"] is True


@pytest.mark.asyncio
async def test_cv_requests_search_multiple_fields(client: AsyncClient, db_session):
    """Test that search works across name, email, AND company."""
    from app.models.cv_request import CvRequest

    requests = [
        CvRequest(
            name="John Acme", email="john@example.com", company="TechCorp", message="M"
        ),
        CvRequest(
            name="Jane Smith", email="jane@acme.com", company="DevOps Inc", message="M"
        ),
        CvRequest(
            name="Bob Lee", email="bob@test.com", company="Acme Solutions", message="M"
        ),
    ]
    for req in requests:
        db_session.add(req)
    await db_session.commit()

    # Search for "acme" should match name, email, AND company
    response = await client.get(f"{settings.api_prefix}/admin/cv/requests?search=acme")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3  # All three have "acme" in different fields


@pytest.mark.asyncio
async def test_posts_large_dataset_pagination(client: AsyncClient, db_session):
    """Test pagination with large dataset (100+ items)."""
    from app.models.post import Post

    # Create 150 posts
    for i in range(150):
        db_session.add(
            Post(
                title=f"Post {i:03d}",
                slug=f"post-{i:03d}",
                content="Content",
                language="en",
                published=True,
            )
        )
    await db_session.commit()

    # Test various pages
    response = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=50")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 150
    assert len(data["items"]) == 50
    assert data["total_pages"] == 3

    # Last page should have exactly 50
    response = await client.get(f"{settings.api_prefix}/posts?page=3&page_size=50")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 50

    # Page 4 should be empty
    response = await client.get(f"{settings.api_prefix}/posts?page=4&page_size=50")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_posts_max_page_size_enforced(client: AsyncClient, db_session):
    """Test that page_size is capped at 100."""
    from app.models.post import Post

    # Create 150 posts
    for i in range(150):
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

    # Request page_size > 100 should be rejected
    response = await client.get(f"{settings.api_prefix}/posts?page_size=150")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tags_sort_by_name_and_count(client: AsyncClient, db_session):
    """Test tags can be sorted by both name and count."""
    from app.models.post import Post

    posts = [
        Post(
            title="P1",
            slug="p1",
            content="C",
            language="en",
            published=True,
            tags=["python", "ai", "ml"],
        ),
        Post(
            title="P2",
            slug="p2",
            content="C",
            language="en",
            published=True,
            tags=["python", "backend"],
        ),
        Post(
            title="P3",
            slug="p3",
            content="C",
            language="en",
            published=True,
            tags=["javascript"],
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    # Sort by count desc (python should be first with count=2)
    response = await client.get(
        f"{settings.api_prefix}/tags?sort_by=count&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "python"
    assert data["items"][0]["count"] == 2

    # Sort by name asc
    response = await client.get(
        f"{settings.api_prefix}/tags?sort_by=name&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    # "ai" should be first alphabetically
    assert data["items"][0]["name"] == "ai"


@pytest.mark.asyncio
async def test_posts_search_in_title_and_summary(client: AsyncClient, db_session):
    """Test that search works in BOTH title and summary."""
    from app.models.post import Post

    posts = [
        Post(
            title="React Tutorial",
            slug="p1",
            content="C",
            summary="Learn basics",
            language="en",
            published=True,
        ),
        Post(
            title="Guide",
            slug="p2",
            content="C",
            summary="React advanced",
            language="en",
            published=True,
        ),
        Post(
            title="Vue.js",
            slug="p3",
            content="C",
            summary="Framework",
            language="en",
            published=True,
        ),
    ]
    for p in posts:
        db_session.add(p)
    await db_session.commit()

    # Search for "React" should find both (title and summary)
    response = await client.get(f"{settings.api_prefix}/posts?search=React")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_cv_versions_search_filename_and_version(client: AsyncClient, db_session):
    """Test CV versions search works on filename AND version."""
    from app.models.cv_document import CvDocument

    documents = [
        CvDocument(filename="cv_2023.pdf", version="1.0", data=b"data", is_active=True),
        CvDocument(
            filename="resume.pdf", version="2023-v2", data=b"data", is_active=False
        ),
        CvDocument(filename="doc.pdf", version="3.0", data=b"data", is_active=False),
    ]
    for doc in documents:
        db_session.add(doc)
    await db_session.commit()

    # Search for "2023" should match both filename and version
    response = await client.get(f"{settings.api_prefix}/admin/cv/versions?search=2023")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_posts_combined_all_params(client: AsyncClient, db_session):
    """Test using pagination, sorting, and search ALL together."""
    from app.models.post import Post

    # Create many posts with "python" keyword
    for i in range(25):
        db_session.add(
            Post(
                title=f"Python Tutorial {i}",
                slug=f"python-{i}",
                content="Content",
                language="en",
                published=True,
            )
        )
    # Create posts without keyword
    for i in range(10):
        db_session.add(
            Post(
                title=f"JavaScript {i}",
                slug=f"js-{i}",
                content="Content",
                language="en",
                published=True,
            )
        )
    await db_session.commit()

    # Search "python", sort by title asc, page 2, page_size 10
    response = await client.get(
        f"{settings.api_prefix}/posts?search=python&sort_by=title&sort_order=asc&page=2&page_size=10"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 25  # Only python posts
    assert len(data["items"]) == 10
    assert data["page"] == 2
    assert data["total_pages"] == 3

    # Items should be sorted by title
    assert "Python Tutorial 1" in data["items"][0]["title"]


@pytest.mark.asyncio
async def test_pagination_response_schema_validation(client: AsyncClient, db_session):
    """Test that paginated response has correct schema."""
    from app.models.post import Post

    db_session.add(
        Post(title="Test", slug="test", content="C", language="en", published=True)
    )
    await db_session.commit()

    response = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()

    # Validate all required fields exist
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data

    # Validate types
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    assert isinstance(data["page"], int)
    assert isinstance(data["page_size"], int)
    assert isinstance(data["total_pages"], int)

    # Validate values
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total"] == 1
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_empty_search_with_pagination(client: AsyncClient, db_session):
    """Test empty search doesn't break pagination."""
    from app.models.post import Post

    for i in range(15):
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

    # Empty search with pagination params
    response = await client.get(
        f"{settings.api_prefix}/posts?search=&page=1&page_size=10"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 15
    assert len(data["items"]) == 10


@pytest.mark.asyncio
async def test_cv_requests_pagination_edge_at_10(client: AsyncClient, db_session):
    """Test CV requests with exactly 10 items (1 full page)."""
    from app.models.cv_request import CvRequest

    for i in range(10):
        db_session.add(
            CvRequest(
                name=f"User {i}",
                email=f"user{i}@test.com",
                company="Company",
                message="Test",
            )
        )
    await db_session.commit()

    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?page=1&page_size=10"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["items"]) == 10
    assert data["total_pages"] == 1

    # Page 2 should be empty
    response = await client.get(
        f"{settings.api_prefix}/admin/cv/requests?page=2&page_size=10"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_tags_with_no_posts(client: AsyncClient, db_session):
    """Test tags endpoint when no posts exist."""
    response = await client.get(f"{settings.api_prefix}/tags")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 1
