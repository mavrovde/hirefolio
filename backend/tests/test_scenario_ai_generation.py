import pytest
from unittest.mock import patch, MagicMock
from app.services.ai import generate_full_post, suggest_post_details

# Scenario: AI Generation Success
# Expected: Returns dictionary with post content

@pytest.mark.asyncio
async def test_scenario_ai_generation_success():
    mock_response = MagicMock()
    mock_response.text = '{"title": "AI Post", "slug": "ai-post", "summary": "Summary", "content": "Generated content.", "tags": ["ai"]}'
    
    mock_client = MagicMock()
    # Mock synchronous generation call (Gemini SDK style)
    mock_client.models.generate_content.return_value = mock_response
    
    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        # Mock embeddings for unrelated calls? No, generate_full_post is pure AI usually.
        # But it might call other helpers.
        
        result = await generate_full_post(topic="AI", user_api_key="fake")
        
        assert result is not None
        assert result["title"] == "AI Post"
        assert result["tags"] == ["ai"]

# Scenario: Suggest Post Details Success
# Expected: Returns details

@pytest.mark.asyncio
async def test_scenario_ai_suggest_details_success():
    mock_response = MagicMock()
    mock_response.text = '{"title": "Suggested Title", "summary": "Summary", "slug": "slug", "tags": []}'
    
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
         result = await suggest_post_details(content="some content", user_api_key="fake")
         
         assert result["title"] == "Suggested Title"
