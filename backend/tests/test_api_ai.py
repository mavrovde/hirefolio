import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_suggest_tags_endpoint(client: AsyncClient):
    """Test suggest tags endpoint with mocked AI service."""
    
    # We need to mock the import inside the route function or the function it calls
    # Since we are testing the API, we can mock app.services.ai.suggest_tags
    
    mock_tags = ["mocked", "ai", "tags"]
    
    with patch("app.services.ai.suggest_tags", return_value=mock_tags) as mock_suggest:
        response = await client.post(
            "/api/posts/suggest-tags",
            json={"title": "Test Title", "content": "Test Content"}
        )
        
        assert response.status_code == 200
        assert response.json() == {"tags": mock_tags}
        mock_suggest.assert_called_once() # Ensure generic signature match
