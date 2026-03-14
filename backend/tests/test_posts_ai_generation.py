from app.config import settings
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_generate_post_retry_on_slug_collision(client: AsyncClient, mock_embedding, mocker):
    """Scenario: AI generates a post that has a slug identical to an existing post."""
    mocker.patch("app.services.ai.generate_full_post", return_value={
        "title": "AI Title",
        "content": "AI Content",
        "slug": "ai-slug",
        "summary": "AI Summary",
        "tags": ["ai"]
    })

    post_data = {
        "title": "Existing",
        "slug": "ai-slug",
        "content": "Content",
    }
    await client.post(f"{settings.api_prefix}/posts", json=post_data)

    response = await client.post(f"{settings.api_prefix}/posts/generate", json={"topic": "Test AI"})
    
    assert response.status_code == 200
    assert response.json()["slug"].startswith("ai-slug-")

@pytest.mark.asyncio
async def test_generate_post_ai_returns_none(client: AsyncClient, mock_embedding, mocker):
    """Scenario: AI generation service fails and returns None."""
    mocker.patch("app.services.ai.generate_full_post", return_value=None)
    response = await client.post(f"{settings.api_prefix}/posts/generate", json={"topic": "Test AI"})
    assert response.status_code == 500

@pytest.mark.asyncio
async def test_generate_post_successful(client: AsyncClient, mock_embedding, mocker):
    """Scenario: AI generates a valid post correctly."""
    mocker.patch("app.services.ai.generate_full_post", return_value={
        "title": "Good AI Title",
        "content": "Good AI Content",
        "slug": "good-ai-slug",
        "summary": "Summary",
        "tags": []
    })
    response = await client.post(f"{settings.api_prefix}/posts/generate", json={"topic": "Test AI"})
    assert response.status_code == 200
    assert response.json()["slug"] == "good-ai-slug"
