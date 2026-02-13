
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services import ai
from app.config import settings

@pytest.mark.asyncio
async def test_get_gemini_client_no_key():
    """Test _get_gemini_client returns None when no key."""
    with patch("app.services.ai.settings.gemini_api_key", ""), \
         patch("app.services.ai.HAS_GEMINI", True):
        client = ai._get_gemini_client()
        assert client is None

@pytest.mark.asyncio
async def test_get_gemini_client_no_module():
    """Test _get_gemini_client returns None when module missing."""
    with patch("app.services.ai.settings.gemini_api_key", "key"), \
         patch("app.services.ai.HAS_GEMINI", False):
        client = ai._get_gemini_client()
        assert client is None

@pytest.mark.asyncio
async def test_get_gemini_client_error():
    """Test _get_gemini_client handles exception."""
    with patch("app.services.ai.settings.gemini_api_key", "key"), \
         patch("app.services.ai.HAS_GEMINI", True), \
         patch("app.services.ai.genai.Client", side_effect=Exception("Boom")):
        client = ai._get_gemini_client()
        assert client is None

@pytest.mark.asyncio
async def test_generate_text_gemini_success():
    """Test _generate_text_gemini success path."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Generated Text"
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai._generate_text_gemini("prompt")
        assert result == "Generated Text"
        mock_client.models.generate_content.assert_called_with(
            model='gemini-2.0-flash', contents="prompt"
        )

@pytest.mark.asyncio
async def test_generate_text_gemini_fallback():
    """Test _generate_text_gemini fallback to 1.5."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Fallback Text"
    
    # First call raises, second succeeds
    mock_client.models.generate_content.side_effect = [Exception("2.0 fail"), mock_response]

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai._generate_text_gemini("prompt")
        assert result == "Fallback Text"
        assert mock_client.models.generate_content.call_count == 2

@pytest.mark.asyncio
async def test_generate_text_gemini_fail_all():
    """Test _generate_text_gemini returns None on total failure."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("All fail")

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai._generate_text_gemini("prompt")
        assert result is None

@pytest.mark.asyncio
async def test_chat_with_gemini_not_configured():
    with patch("app.services.ai._get_gemini_client", return_value=None):
        res = await ai.chat_with_gemini("hello")
        assert "not configured" in res

@pytest.mark.asyncio
async def test_chat_with_gemini_success():
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Chat Response"
    mock_chat.send_message.return_value = mock_response
    mock_client.models.start_chat.return_value = mock_chat

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        history = [{"role": "user", "content": "hi"}]
        res = await ai.chat_with_gemini("hello", history)
        assert res == "Chat Response"
        
        # Verify history conversion
        expected_history = [{"role": "user", "parts": ["hi"]}]
        mock_client.models.start_chat.assert_called_with(
            model='gemini-2.0-flash',
            history=expected_history
        )

@pytest.mark.asyncio
async def test_chat_with_gemini_fallback():
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Fallback Chat"
    mock_chat.send_message.return_value = mock_response
    
    # First start_chat fails, second succeeds
    mock_client.models.start_chat.side_effect = [Exception("2.0 fail"), mock_chat]

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.chat_with_gemini("hello")
        assert res == "Fallback Chat"
        assert mock_client.models.start_chat.call_count == 2
        args, kwargs = mock_client.models.start_chat.call_args_list[1]
        assert kwargs['model'] == 'gemini-1.5-flash'

@pytest.mark.asyncio
async def test_chat_with_gemini_error():
    mock_client = MagicMock()
    mock_client.models.start_chat.side_effect = Exception("Total fail")

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.chat_with_gemini("hello")

@pytest.mark.asyncio
async def test_suggest_tags_gemini_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '["tag1", "tag2"]'
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        # We also need to mock settings if we want to ensure no Ollama config needed
        tags = await ai.suggest_tags("Title", "Content")
        assert tags == ["tag1", "tag2"]
        # Verify prompt contained title/content
        call_args = mock_client.models.generate_content.call_args
        assert "Title" in call_args.kwargs['contents']

@pytest.mark.asyncio
async def test_suggest_tags_gemini_json_markdown():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '```json\n["tag1", "tag2"]\n```'
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        tags = await ai.suggest_tags("Title", "Content")
        assert tags == ["tag1", "tag2"]

@pytest.mark.asyncio
async def test_suggest_tags_fallback_ollama():
    # Gemini returns None
    with patch("app.services.ai._generate_text_gemini", return_value=None), \
         patch("app.services.ai.httpx.AsyncClient") as mock_http:
        
        mock_client_instance = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_client_instance
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '{"tags": ["ollama1"]}'}
        mock_client_instance.post.return_value = mock_response

        tags = await ai.suggest_tags("Title", "Content")
        assert tags == ["ollama1"]

@pytest.mark.asyncio
async def test_suggest_post_details_gemini_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Simple valid JSON
    mock_response.text = '{"title": "T", "slug": "s", "summary": "sum", "tags": ["t1"]}'
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        details = await ai.suggest_post_details("Content")
        assert details["title"] == "T"
        assert details["tags"] == ["t1"]

@pytest.mark.asyncio
async def test_suggest_field_gemini_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Suggested Title"
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.suggest_field("Content", "title")
        assert res["title"] == "Suggested Title"

@pytest.mark.asyncio
async def test_generate_full_post_gemini_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    content_json = {
        "title": "Full Post",
        "slug": "full-post",
        "summary": "Sum",
        "tags": ["AI"],
        "content": "# Markdown"
    }
    import json
    mock_response.text = json.dumps(content_json)
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.generate_full_post("Topic")
        assert res["title"] == "Full Post"
        assert res["content"] == "# Markdown"

@pytest.mark.asyncio
async def test_generate_full_post_robust_parsing():
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Malformed text around JSON
    mock_response.text = 'Sure! Here is the JSON:\n```json\n{"title": "Full Post", "slug": "s", "summary": "sum", "tags": ["t"], "content": "c"}\n```'
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.generate_full_post("Topic")
        assert res["title"] == "Full Post"

@pytest.mark.asyncio
async def test_generate_full_post_fallback_fail():
    # Both fail
    with patch("app.services.ai._generate_text_gemini", return_value=None), \
         patch("app.services.ai.httpx.AsyncClient") as mock_http:
        
        mock_client_instance = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.side_effect = Exception("Ollama bad")

        res = await ai.generate_full_post("Topic")
        assert res == {}

