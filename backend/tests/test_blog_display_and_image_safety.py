"""
Tests for blog display: initial load 10, load more 5.
These tests verify the pagination behavior expected by the frontend blog component.
"""

import pytest
from httpx import AsyncClient

from app.config import settings

API_PREFIX = settings.api_prefix


@pytest.mark.asyncio
async def test_blog_initial_load_10_then_load_more_5(
    client: AsyncClient, mock_embedding
):
    """Test the blog visitor flow: load 10 initially, then 5 more at a time."""
    # Create 18 published posts
    for i in range(18):
        await client.post(
            f"{API_PREFIX}/posts",
            json={
                "title": f"Blog Post {i:02d}",
                "slug": f"blog-post-{i:02d}",
                "content": f"Content for post {i}",
                "summary": f"Summary {i}",
                "published": True,
                "language": "en",
            },
        )

    # Initial load: page 1, page_size=10 (visitor opens the page)
    response = await client.get(
        f"{API_PREFIX}/posts?page=1&page_size=10&published_only=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 18
    assert len(data["items"]) == 10
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total_pages"] == 2

    # Load more: page 2, page_size=5 (visitor clicks "Load More")
    response = await client.get(
        f"{API_PREFIX}/posts?page=2&page_size=5&published_only=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert data["page"] == 2
    assert data["page_size"] == 5
    assert data["total_pages"] == 4  # ceil(18/5) = 4

    # Load more again: page 3, page_size=5
    response = await client.get(
        f"{API_PREFIX}/posts?page=3&page_size=5&published_only=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert data["page"] == 3

    # Load more: page 4, page_size=5 (last page)
    response = await client.get(
        f"{API_PREFIX}/posts?page=4&page_size=5&published_only=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3  # 18 - 5*3 = 3 remaining


@pytest.mark.asyncio
async def test_blog_published_only_filter(client: AsyncClient, mock_embedding):
    """Test that only published posts are returned for visitors."""
    # Create mix of published and draft posts
    for i in range(5):
        await client.post(
            f"{API_PREFIX}/posts",
            json={
                "title": f"Published Post {i}",
                "slug": f"pub-{i}",
                "content": f"Content {i}",
                "published": True,
            },
        )
    for i in range(3):
        await client.post(
            f"{API_PREFIX}/posts",
            json={
                "title": f"Draft Post {i}",
                "slug": f"draft-{i}",
                "content": f"Draft content {i}",
                "published": False,
            },
        )

    # Visitor request (published_only=true)
    response = await client.get(f"{API_PREFIX}/posts?published_only=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5  # Only published posts


@pytest.mark.asyncio
async def test_blog_default_sort_newest_first(client: AsyncClient, mock_embedding):
    """Test that blog posts are sorted newest first by default."""
    for i in range(3):
        await client.post(
            f"{API_PREFIX}/posts",
            json={
                "title": f"Post {i}",
                "slug": f"post-{i}",
                "content": f"Content {i}",
                "published": True,
            },
        )

    response = await client.get(f"{API_PREFIX}/posts?published_only=true")
    assert response.status_code == 200
    data = response.json()
    # Default sort is created_at desc, so newest first
    assert data["items"][0]["title"] == "Post 2"
    assert data["items"][2]["title"] == "Post 0"
