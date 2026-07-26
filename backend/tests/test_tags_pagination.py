from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_tags_pagination_empty(client: AsyncClient):
    """Test tags pagination with no posts."""
    response = await client.get(f"{settings.api_prefix}/tags")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_tags_list_with_counts(client: AsyncClient, mock_embedding):
    """Test listing tags with usage counts."""
    # Create posts with tags
    posts = [
        {
            "title": "Post 1",
            "slug": "post-1",
            "content": "Content",
            "tags": ["docker", "python"],
            "published": True,
        },
        {
            "title": "Post 2",
            "slug": "post-2",
            "content": "Content",
            "tags": ["docker", "kubernetes"],
            "published": True,
        },
        {
            "title": "Post 3",
            "slug": "post-3",
            "content": "Content",
            "tags": ["python"],
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            await client.post(f"{settings.api_prefix}/posts", json=post)

    # List tags
    response = await client.get(f"{settings.api_prefix}/tags")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3  # docker, python, kubernetes

    # Find counts
    tags_dict = {tag["name"]: tag["count"] for tag in data["items"]}
    assert tags_dict["docker"] == 2
    assert tags_dict["python"] == 2
    assert tags_dict["kubernetes"] == 1


@pytest.mark.asyncio
async def test_tags_search(client: AsyncClient, mock_embedding):
    """Test searching tags by name."""
    # Create posts with tags
    posts = [
        {
            "title": "Post 1",
            "slug": "post-1",
            "content": "Content",
            "tags": ["docker-compose", "docker-swarm", "python"],
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            await client.post(f"{settings.api_prefix}/posts", json=post)

    # Search for "docker"
    response = await client.get(f"{settings.api_prefix}/tags?search=docker")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # docker-compose, docker-swarm
    tag_names = [tag["name"] for tag in data["items"]]
    assert "docker-compose" in tag_names
    assert "docker-swarm" in tag_names
    assert "python" not in tag_names


@pytest.mark.asyncio
async def test_tags_search_case_insensitive(client: AsyncClient, mock_embedding):
    """Test that tag search is case-insensitive."""
    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Test",
                "slug": "test",
                "content": "Content",
                "tags": ["Docker", "Python"],
                "published": True,
            },
        )

    # Search with lowercase
    response = await client.get(f"{settings.api_prefix}/tags?search=docker")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1

    # Search with uppercase
    response = await client.get(f"{settings.api_prefix}/tags?search=DOCKER")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_tags_sort_by_name(client: AsyncClient, mock_embedding):
    """Test sorting tags by name."""
    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Test",
                "slug": "test",
                "content": "Content",
                "tags": ["zebra", "alpha", "beta"],
                "published": True,
            },
        )

    # Sort by name ascending
    response = await client.get(
        f"{settings.api_prefix}/tags?sort_by=name&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "alpha"
    assert data["items"][1]["name"] == "beta"
    assert data["items"][2]["name"] == "zebra"

    # Sort by name descending
    response = await client.get(
        f"{settings.api_prefix}/tags?sort_by=name&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "zebra"
    assert data["items"][2]["name"] == "alpha"


@pytest.mark.asyncio
async def test_tags_sort_by_count(client: AsyncClient, mock_embedding):
    """Test sorting tags by usage count."""
    posts = [
        {
            "title": "Post 1",
            "slug": "post-1",
            "content": "Content",
            "tags": ["common"],
            "published": True,
        },
        {
            "title": "Post 2",
            "slug": "post-2",
            "content": "Content",
            "tags": ["common", "rare"],
            "published": True,
        },
        {
            "title": "Post 3",
            "slug": "post-3",
            "content": "Content",
            "tags": ["common"],
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            await client.post(f"{settings.api_prefix}/posts", json=post)

    # Sort by count descending (default)
    response = await client.get(
        f"{settings.api_prefix}/tags?sort_by=count&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "common"
    assert data["items"][0]["count"] == 3
    assert data["items"][1]["name"] == "rare"
    assert data["items"][1]["count"] == 1

    # Sort by count ascending
    response = await client.get(
        f"{settings.api_prefix}/tags?sort_by=count&sort_order=asc"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "rare"
    assert data["items"][1]["name"] == "common"


@pytest.mark.asyncio
async def test_tags_pagination(client: AsyncClient, mock_embedding):
    """Test tags pagination."""
    # Create a post with many tags
    tags = [f"tag{i}" for i in range(15)]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Test",
                "slug": "test",
                "content": "Content",
                "tags": tags[:5],  # Only 5 tags allowed, so create multiple posts
                "published": True,
            },
        )
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Test2",
                "slug": "test2",
                "content": "Content",
                "tags": tags[5:10],
                "published": True,
            },
        )
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Test3",
                "slug": "test3",
                "content": "Content",
                "tags": tags[10:15],
                "published": True,
            },
        )

    # Get first page
    response = await client.get(f"{settings.api_prefix}/tags?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 15
    assert len(data["items"]) == 10
    assert data["total_pages"] == 2

    # Get second page
    response = await client.get(f"{settings.api_prefix}/tags?page=2&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5


@pytest.mark.asyncio
async def test_tags_combined_search_sort_pagination(
    client: AsyncClient, mock_embedding
):
    """Test combining search, sort, and pagination for tags."""
    # Create posts with docker-related tags
    posts = [
        {
            "title": "Post 1",
            "slug": "post-1",
            "content": "Content",
            "tags": ["docker-compose", "docker"],
            "published": True,
        },
        {
            "title": "Post 2",
            "slug": "post-2",
            "content": "Content",
            "tags": ["docker-swarm", "python"],
            "published": True,
        },
        {
            "title": "Post 3",
            "slug": "post-3",
            "content": "Content",
            "tags": ["docker", "docker-cli"],
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            await client.post(f"{settings.api_prefix}/posts", json=post)

    # Search for "docker", sort by name asc, page_size=2
    response = await client.get(
        f"{settings.api_prefix}/tags?search=docker&sort_by=name&sort_order=asc&page=1&page_size=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4  # docker, docker-compose, docker-swarm, docker-cli
    assert len(data["items"]) == 2
    assert data["items"][0]["name"] == "docker"
    assert data["items"][1]["name"] == "docker-cli"

    # Get second page
    response = await client.get(
        f"{settings.api_prefix}/tags?search=docker&sort_by=name&sort_order=asc&page=2&page_size=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["items"][0]["name"] == "docker-compose"
    assert data["items"][1]["name"] == "docker-swarm"


@pytest.mark.asyncio
async def test_tags_no_results_search(client: AsyncClient, mock_embedding):
    """Test search with no matching tags."""
    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post(
            f"{settings.api_prefix}/posts",
            json={
                "title": "Test",
                "slug": "test",
                "content": "Content",
                "tags": ["python"],
                "published": True,
            },
        )

    response = await client.get(f"{settings.api_prefix}/tags?search=NoMatchHere")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
