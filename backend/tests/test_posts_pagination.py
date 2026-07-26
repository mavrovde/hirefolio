import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_pagination_basic(client: AsyncClient, mock_embedding):
    """Test basic pagination functionality."""
    # Create 15 posts
    for i in range(15):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": f"Post {i}",
                "slug": f"post-{i}",
                "content": f"Content {i}",
                "published": True,
            },
        )

    # Request first page (default page_size=10)
    response = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 15
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total_pages"] == 2
    assert len(data["items"]) == 10

    # Request second page
    response = await client.get(f"{settings.api_prefix}/posts?page=2&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert len(data["items"]) == 5  # Only 5 items on last page


@pytest.mark.asyncio
async def test_pagination_page_size_limits(client: AsyncClient, mock_embedding):
    """Test page_size limits."""
    # Create 5 posts
    # Create 5 posts
    for i in range(5):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": f"Post {i}",
                "slug": f"post-{i}",
                "content": f"Content {i}",
                "published": True,
            },
        )

    # Test with page_size=2
    response = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total_pages"] == 3

    # Test maximum page_size=100
    response = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=100")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5  # All items on one page


@pytest.mark.asyncio
async def test_pagination_out_of_bounds(client: AsyncClient, mock_embedding):
    """Test requesting page beyond available pages."""
    # Create 5 posts
    # Create 5 posts
    for i in range(5):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": f"Post {i}",
                "slug": f"post-{i}",
                "content": f"Content {i}",
                "published": True,
            },
        )

    # Request page 999
    response = await client.get(f"{settings.api_prefix}/posts?page=999&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 999
    assert data["items"] == []  # Empty results for out-of-bounds page


@pytest.mark.asyncio
async def test_sorting_by_field(client: AsyncClient, mock_embedding):
    """Test sorting by different fields."""
    # Create posts with different titles
    posts = [
        {"title": "Zebra", "slug": "zebra", "content": "Z", "published": True},
        {"title": "Alpha", "slug": "alpha", "content": "A", "published": True},
        {"title": "Beta", "slug": "beta", "content": "B", "published": True},
    ]

    for post in posts:
        await client.post(f"{settings.api_prefix}/posts", json=post)

    # Sort by title ascending
    response = await client.get(
        f"{settings.api_prefix}/posts?sort_by=title&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["title"] == "Alpha"
    assert data["items"][1]["title"] == "Beta"
    assert data["items"][2]["title"] == "Zebra"

    # Sort by title descending
    response = await client.get(
        f"{settings.api_prefix}/posts?sort_by=title&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["title"] == "Zebra"
    assert data["items"][1]["title"] == "Beta"
    assert data["items"][2]["title"] == "Alpha"


@pytest.mark.asyncio
async def test_sorting_by_created_at(client: AsyncClient, mock_embedding):
    """Test sorting by created_at (default sort)."""
    # Create posts in sequence
    # Create posts in sequence
    for i in range(3):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": f"Post {i}",
                "slug": f"post-{i}",
                "content": f"Content {i}",
                "published": True,
            },
        )

    # Default sort is created_at desc (newest first)
    response = await client.get(
        f"{settings.api_prefix}/posts?sort_by=created_at&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    # Most recent post should be first
    assert data["items"][0]["title"] == "Post 2"

    # Sort ascending (oldest first)
    response = await client.get(
        f"{settings.api_prefix}/posts?sort_by=created_at&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["title"] == "Post 0"


@pytest.mark.asyncio
async def test_sorting_invalid_field(client: AsyncClient, mock_embedding):
    """Test sorting with invalid field falls back to default."""
    # Create posts
    # Create posts in sequence
    for i in range(3):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": f"Post {i}",
                "slug": f"post-{i}",
                "content": f"Content {i}",
                "published": True,
            },
        )

    # Try to sort by non-existent field
    response = await client.get(
        f"{settings.api_prefix}/posts?sort_by=invalid_field&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    # Should fall back to created_at desc
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_search_functionality(client: AsyncClient, mock_embedding):
    """Test search in title and summary."""
    posts = [
        {
            "title": "Docker Tutorial",
            "slug": "docker-tutorial",
            "summary": "Learn Docker basics",
            "content": "Content",
            "published": True,
        },
        {
            "title": "Kubernetes Guide",
            "slug": "k8s-guide",
            "summary": "Docker and Kubernetes",
            "content": "Content",
            "published": True,
        },
        {
            "title": "Python Tips",
            "slug": "python-tips",
            "summary": "Python best practices",
            "content": "Content",
            "published": True,
        },
    ]

    for post in posts:
        await client.post(f"{settings.api_prefix}/posts", json=post)

    # Search for "Docker" - should match 2 posts
    response = await client.get(f"{settings.api_prefix}/posts?search=Docker")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    titles = [item["title"] for item in data["items"]]
    assert "Docker Tutorial" in titles
    assert "Kubernetes Guide" in titles

    # Search for "Python" - should match 1 post
    response = await client.get(f"{settings.api_prefix}/posts?search=Python")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Python Tips"


@pytest.mark.asyncio
async def test_search_case_insensitive(client: AsyncClient, mock_embedding):
    """Test that search is case-insensitive."""
    await client.post(
        f"{settings.api_prefix}/posts",
        json={
            "title": "Docker Tutorial",
            "slug": "docker",
            "content": "Content",
            "published": True,
        },
    )

    # Search with lowercase
    response = await client.get(f"{settings.api_prefix}/posts?search=docker")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1

    # Search with uppercase
    response = await client.get(f"{settings.api_prefix}/posts?search=DOCKER")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient, mock_embedding):
    """Test search with no matching results."""
    # Create posts
    for i in range(3):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": f"Post {i}",
                "slug": f"post-{i}",
                "content": f"Content {i}",
                "published": True,
            },
        )

    response = await client.get(f"{settings.api_prefix}/posts?search=NoMatchHere")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_combined_pagination_search_sort(client: AsyncClient, mock_embedding):
    """Test combining pagination, search, and sorting."""
    posts = [
        {
            "title": "Docker Advanced",
            "slug": "docker-adv",
            "summary": "Advanced Docker",
            "content": "Content",
            "published": True,
        },
        {
            "title": "Docker Basics",
            "slug": "docker-basics",
            "summary": "Docker fundamentals",
            "content": "Content",
            "published": True,
        },
        {
            "title": "Docker Containers",
            "slug": "docker-containers",
            "summary": "Working with containers",
            "content": "Content",
            "published": True,
        },
    ]

    for post in posts:
        await client.post(f"{settings.api_prefix}/posts", json=post)

    # Search for "Docker", sort by title asc, page_size=2
    response = await client.get(
        f"{settings.api_prefix}/posts?search=Docker&sort_by=title&sort_order=asc&page=1&page_size=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["title"] == "Docker Advanced"
    assert data["items"][1]["title"] == "Docker Basics"

    # Get second page
    response = await client.get(
        f"{settings.api_prefix}/posts?search=Docker&sort_by=title&sort_order=asc&page=2&page_size=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Docker Containers"


@pytest.mark.asyncio
async def test_pagination_with_filters(client: AsyncClient, mock_embedding):
    """Test pagination with language and tag filters."""
    posts = [
        {
            "title": "EN Post 1",
            "slug": "en-1",
            "content": "Content",
            "language": "en",
            "published": True,
            "tags": ["docker"],
        },
        {
            "title": "EN Post 2",
            "slug": "en-2",
            "content": "Content",
            "language": "en",
            "published": True,
            "tags": ["python"],
        },
        {
            "title": "DE Post 1",
            "slug": "de-1",
            "content": "Inhalt",
            "language": "de",
            "published": True,
            "tags": ["docker"],
        },
    ]

    for post in posts:
        await client.post(f"{settings.api_prefix}/posts", json=post)

    # Filter by language and tag
    response = await client.get(f"{settings.api_prefix}/posts?lang=en&tag=docker")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["language"] == "en"
    assert "docker" in data["items"][0]["tags"]


@pytest.mark.asyncio
async def test_pagination_empty_page(client: AsyncClient):
    """Test requesting a page when there are no results."""
    response = await client.get(f"{settings.api_prefix}/posts?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 1
