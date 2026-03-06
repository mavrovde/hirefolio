import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services import ai


@pytest.mark.asyncio
async def test_get_gemini_client_no_key():
    """Test behavior when no API key is provided."""
    with (
        patch("app.services.ai.settings.gemini_api_key", ""),
        patch("app.services.ai.HAS_GEMINI", True),
    ):
        client = ai._get_gemini_client(None)
        assert client is None


@pytest.mark.asyncio
async def test_get_gemini_client_no_module():
    """Test behavior when google.genai is not available."""
    with patch("app.services.ai.HAS_GEMINI", False):
        client = ai._get_gemini_client("some-key")
        assert client is None


@pytest.mark.asyncio
async def test_get_gemini_client_exception():
    """Test behavior when client creation raises exception."""
    mock_genai = MagicMock()
    mock_genai.Client.side_effect = Exception("Boom")
    with (
        patch("app.services.ai.HAS_GEMINI", True),
        patch.object(ai, "genai", mock_genai, create=True),
    ):
        client = ai._get_gemini_client("some-key")
        assert client is None


@pytest.mark.asyncio
async def test_generate_text_gemini_fallback(mocker):
    """Test fallback to 1.5-flash when 2.0-flash fails."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Fallback Success"

    # First call failed, second call success
    mock_client.models.generate_content.side_effect = [
        Exception("2.0 failed"),
        mock_response,
    ]

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai._generate_text_gemini("prompt")
        assert result == "Fallback Success"
        assert mock_client.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_generate_text_gemini_total_failure(mocker):
    """Test return None when both models fail."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("All failed")

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai._generate_text_gemini("prompt")
        assert result is None


@pytest.mark.asyncio
async def test_suggest_tags_gemini_success(mocker):
    """Test suggest_tags using Gemini path."""
    with patch(
        "app.services.ai._generate_text_gemini", return_value='["tag1", "tag2"]'
    ):
        tags = await ai.suggest_tags("Title", "Content")
        assert "tag1" in tags
        assert "tag2" in tags


@pytest.mark.asyncio
async def test_suggest_tags_ollama_fallback(mocker):
    """Test suggest_tags using Ollama fallback when Gemini returns None."""
    # Mock httpx for Ollama
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": '["ollama1", "ollama2"]'}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with (
        patch("app.services.ai._generate_text_gemini", return_value=None),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        tags = await ai.suggest_tags("Title", "Content")
        assert "ollama1" in tags


@pytest.mark.asyncio
async def test_suggest_tags_parsing_fallback():
    """Test regex fallback when JSON parsing fails."""
    bad_json = "Here are tags: tagA, tagB."
    with patch("app.services.ai._generate_text_gemini", return_value=bad_json):
        tags = await ai.suggest_tags("Title", "Content")
        assert "taga" in tags
        assert "tagb" in tags


@pytest.mark.asyncio
async def test_suggest_post_details_json_repair():
    """Test suggest_post_details with markdown wrapped JSON."""
    json_resp = (
        '```json\n{"title": "T", "slug": "s", "summary": "sum", "tags": ["t1"]}\n```'
    )
    with patch("app.services.ai._generate_text_gemini", return_value=json_resp):
        details = await ai.suggest_post_details("Content")
        assert details["title"] == "T"
        assert details["tags"] == ["t1"]


@pytest.mark.asyncio
async def test_chat_with_gemini_fallback():
    """Test chat fallback."""
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Chat Success"
    mock_chat.send_message.return_value = mock_response

    # client.chats.create fails first time
    mock_client.chats.create.side_effect = [Exception("2.0 chat failed"), mock_chat]

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai.chat_with_gemini("msg")
        assert result == "Chat Success"
