from app.config import settings
import pytest
from unittest.mock import patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_posts_empty(client: AsyncClient):
    """Test listing posts when database is empty."""
    response = await client.get(f"{settings.api_prefix}/posts")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_create_post(client: AsyncClient, mock_embedding):
    """Test creating a new post."""
    post_data = {
        "title": "Getting Started with Ollama",
        "slug": "getting-started-ollama",
        "content": "Ollama is a great tool for running LLMs locally...",
        "summary": "Learn how to use Ollama",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.post(f"{settings.api_prefix}/posts", json=post_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == post_data["title"]
    assert data["slug"] == post_data["slug"]
    assert data["published"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_post(client: AsyncClient, mock_embedding):
    """Test retrieving a specific post."""
    # Create a post first
    post_data = {
        "title": "Ollama Embeddings",
        "slug": "ollama-embeddings",
        "content": "Using Ollama for embeddings is cost-effective...",
        "summary": "Ollama embeddings guide",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post(f"{settings.api_prefix}/posts", json=post_data)

    # Retrieve the post
    response = await client.get(f"{settings.api_prefix}/posts/ollama-embeddings")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == post_data["title"]
    assert data["slug"] == post_data["slug"]


@pytest.mark.asyncio
async def test_get_post_not_found(client: AsyncClient):
    """Test retrieving a non-existent post."""
    response = await client.get(f"{settings.api_prefix}/posts/non-existent-slug")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_post(client: AsyncClient, mock_embedding):
    """Test updating a post."""
    # Create a post
    post_data = {
        "title": "Original Title",
        "slug": "test-update",
        "content": "Original content",
        "language": "en",
        "published": False,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        resp = await client.post(f"{settings.api_prefix}/posts", json=post_data)
        post_id = resp.json()["id"]

    # Update the post
    update_data = {
        "title": "Updated Title",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.put(f"{settings.api_prefix}/posts/{post_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["published"] is True


@pytest.mark.asyncio
async def test_delete_post(client: AsyncClient, mock_embedding):
    """Test deleting a post."""
    # Create a post
    post_data = {
        "title": "To Be Deleted",
        "slug": "delete-me",
        "content": "This will be deleted",
        "language": "en",
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        resp = await client.post(f"{settings.api_prefix}/posts", json=post_data)
        post_id = resp.json()["id"]

    # Delete the post
    response = await client.delete(f"{settings.api_prefix}/posts/{post_id}")
    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()

    # Verify it's gone
    get_response = await client.get(f"{settings.api_prefix}/posts/{post_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_list_posts_with_filters(client: AsyncClient, mock_embedding):
    """Test listing posts with language and published filters."""
    posts = [
        {
            "title": "EN Published",
            "slug": "en-pub",
            "content": "Content",
            "language": "en",
            "published": True,
        },
        {
            "title": "EN Draft",
            "slug": "en-draft",
            "content": "Content",
            "language": "en",
            "published": False,
        },
        {
            "title": "DE Published",
            "slug": "de-pub",
            "content": "Inhalt",
            "language": "de",
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            await client.post(f"{settings.api_prefix}/posts", json=post)

    # Test published filter
    response = await client.get(f"{settings.api_prefix}/posts?published_only=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert all(p["published"] for p in data["items"])

    # Test language filter
    response = await client.get(f"{settings.api_prefix}/posts?lang=de&published_only=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["language"] == "de"


@pytest.mark.asyncio
async def test_similar_posts(client: AsyncClient, mock_embedding):
    """Test finding similar posts."""
    # Create multiple posts
    posts = [
        {
            "title": "Ollama Guide",
            "slug": "ollama-guide",
            "content": "Ollama tutorial",
            "language": "en",
            "published": True,
        },
        {
            "title": "Docker Tips",
            "slug": "docker-tips",
            "content": "Docker best practices",
            "language": "en",
            "published": True,
        },
    ]

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        for post in posts:
            await client.post(f"{settings.api_prefix}/posts", json=post)

    # Get similar posts
    response = await client.get(f"{settings.api_prefix}/posts/ollama-guide/similar")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_semantic_search(client: AsyncClient, mock_embedding):
    """Test semantic search."""
    # Create a post
    post_data = {
        "title": "Ollama Semantic Search",
        "slug": "ollama-search",
        "content": "How to implement semantic search with Ollama",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        await client.post(f"{settings.api_prefix}/posts", json=post_data)

    # Search
    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.get(
            f"{settings.api_prefix}/posts/search/semantic?q=semantic+search&lang=en"
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_semantic_search_no_embedding(client: AsyncClient):
    """Test semantic search when embedding service is unavailable."""
    with patch("app.api.posts.get_embedding", return_value=None):
        response = await client.get(f"{settings.api_prefix}/posts/search/semantic?q=test")

    assert response.status_code == 400
    assert "unavailable" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_post_by_id(client: AsyncClient, mock_embedding):
    """Test retrieving a post by ID."""
    post_data = {
        "title": "Post for ID Fetch",
        "slug": "id-fetch-test",
        "content": "Content",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        create_resp = await client.post(f"{settings.api_prefix}/posts", json=post_data)
        created_post = create_resp.json()
        post_id = created_post["id"]

    # Fetch by ID
    response = await client.get(f"{settings.api_prefix}/posts/{post_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == post_id
    assert data["title"] == post_data["title"]


@pytest.mark.asyncio
async def test_get_post_by_id_not_found(client: AsyncClient):
    """Test retrieving a non-existent post by ID."""
    response = await client.get(f"{settings.api_prefix}/posts/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_post_by_id(client: AsyncClient, mock_embedding):
    """Test updating a post by ID."""
    post_data = {
        "title": "Original ID Update",
        "slug": "id-update-test",
        "content": "Original Content",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        create_resp = await client.post(f"{settings.api_prefix}/posts", json=post_data)
        post_id = create_resp.json()["id"]

    update_data = {"title": "Updated via ID", "content": "New Content"}

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        response = await client.put(f"{settings.api_prefix}/posts/{post_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == post_id
    assert data["title"] == "Updated via ID"
    assert data["content"] == "New Content"


@pytest.mark.asyncio
async def test_delete_post_by_id(client: AsyncClient, mock_embedding):
    """Test deleting a post by ID."""
    post_data = {
        "title": "ID Delete Test",
        "slug": "id-delete-test",
        "content": "Content",
        "language": "en",
        "published": True,
    }

    with patch("app.api.posts.get_embedding", return_value=mock_embedding):
        create_resp = await client.post(f"{settings.api_prefix}/posts", json=post_data)
        post_id = create_resp.json()["id"]

    # Delete by ID
    response = await client.delete(f"{settings.api_prefix}/posts/{post_id}")
    assert response.status_code == 200

    # Verify gone
    get_response = await client.get(f"{settings.api_prefix}/posts/{post_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_suggest_tags_endpoint(client: AsyncClient):
    """Test the suggest-tags endpoint."""
    with patch("app.services.ai.suggest_tags", return_value=["tag1", "tag2"]) as mock:
        response = await client.post(
            f"{settings.api_prefix}/posts/suggest-tags", json={"title": "T", "content": "C"}
        )
        assert response.status_code == 200
        assert response.json() == {"tags": ["tag1", "tag2"]}
        mock.assert_called_once()


@pytest.mark.asyncio
async def test_suggest_details_endpoint_all(client: AsyncClient):
    """Test the suggest-details endpoint with field=all."""
    mock_res = {"title": "T", "slug": "s", "summary": "Sum", "tags": []}
    with patch("app.services.ai.suggest_post_details", return_value=mock_res) as mock:
        response = await client.post(
            f"{settings.api_prefix}/posts/suggest-details", json={"content": "C", "field": "all"}
        )
        assert response.status_code == 200
        assert response.json() == mock_res
        mock.assert_called_once()


@pytest.mark.asyncio
async def test_suggest_details_endpoint_single_field(client: AsyncClient):
    """Test the suggest-details endpoint with a specific field."""
    with patch(
        "app.services.ai.suggest_field", return_value={"title": "Suggested"}
    ) as mock:
        response = await client.post(
            f"{settings.api_prefix}/posts/suggest-details", json={"content": "C", "field": "title"}
        )
        assert response.status_code == 200
        assert response.json() == {"title": "Suggested"}
        mock.assert_called_once()
