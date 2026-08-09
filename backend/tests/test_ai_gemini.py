from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from google.genai import errors as genai_errors

from app.services import ai


def _model_not_found_error() -> genai_errors.APIError:
    """Build a genuine 'model unavailable' (HTTP 404) Gemini API error."""
    return genai_errors.ClientError(
        404,
        {"error": {"status": "NOT_FOUND", "message": "model is not found"}},
    )


@pytest.mark.asyncio
async def test_get_gemini_client_no_key():
    """Test _get_gemini_client returns None when no key."""
    with (
        patch("app.services.ai.settings.gemini_api_key", ""),
        patch("app.services.ai.HAS_GEMINI", True),
    ):
        client = ai._get_gemini_client()
        assert client is None


@pytest.mark.asyncio
async def test_get_gemini_client_no_module():
    """Test _get_gemini_client returns None when module missing."""
    with (
        patch("app.services.ai.settings.gemini_api_key", "key"),
        patch("app.services.ai.HAS_GEMINI", False),
    ):
        client = ai._get_gemini_client()
        assert client is None


@pytest.mark.asyncio
async def test_get_gemini_client_error():
    """Test _get_gemini_client handles exception."""
    with (
        patch("app.services.ai.settings.gemini_api_key", "key"),
        patch("app.services.ai.HAS_GEMINI", True),
        patch("app.services.ai.genai", create=True) as mock_genai,
    ):
        mock_genai.Client.side_effect = Exception("Boom")
        client = ai._get_gemini_client()
        assert client is None


@pytest.mark.asyncio
async def test_generate_text_gemini_success():
    """Test _generate_text_gemini success path."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    type(mock_response).text = PropertyMock(return_value="Generated Text")
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai._generate_text_gemini("prompt")
        assert result == "Generated Text"
        # Model name is config-driven (default cheap flash tier), not hardcoded.
        mock_client.models.generate_content.assert_called_with(
            model=ai.settings.gemini_model, contents="prompt"
        )


@pytest.mark.asyncio
async def test_generate_text_gemini_model_is_config_driven():
    """The primary model comes from settings; overriding it changes the call."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    type(mock_response).text = PropertyMock(return_value="ok")
    mock_client.models.generate_content.return_value = mock_response

    with (
        patch("app.services.ai._get_gemini_client", return_value=mock_client),
        patch("app.services.ai.settings.gemini_model", "gemini-custom-model"),
    ):
        await ai._generate_text_gemini("prompt")
        mock_client.models.generate_content.assert_called_once_with(
            model="gemini-custom-model", contents="prompt"
        )


@pytest.mark.asyncio
async def test_generate_text_gemini_fallback_on_model_unavailable():
    """Fallback model is used ONLY on a genuine 'model unavailable' (404) error."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    type(mock_response).text = PropertyMock(return_value="Fallback Text")

    # Primary model 404s (unavailable), fallback succeeds.
    mock_client.models.generate_content.side_effect = [
        _model_not_found_error(),
        mock_response,
    ]

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai._generate_text_gemini("prompt")
        assert result == "Fallback Text"
        assert mock_client.models.generate_content.call_count == 2
        _args, kwargs = mock_client.models.generate_content.call_args_list[1]
        assert kwargs["model"] == ai.settings.gemini_model_fallback


@pytest.mark.asyncio
async def test_generate_text_gemini_generic_error_no_second_call():
    """A generic exception must NOT trigger a second (billable) Gemini call."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("transient 500")

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai._generate_text_gemini("prompt")
        assert result is None
        # Exactly one Gemini call — no double-billing on generic errors.
        assert mock_client.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_generate_text_gemini_no_fallback_when_same_model():
    """No retry when the fallback model equals (or is unset for) the primary."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = _model_not_found_error()

    with (
        patch("app.services.ai._get_gemini_client", return_value=mock_client),
        patch("app.services.ai.settings.gemini_model", "gemini-x"),
        patch("app.services.ai.settings.gemini_model_fallback", "gemini-x"),
    ):
        result = await ai._generate_text_gemini("prompt")
        assert result is None
        assert mock_client.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_generate_text_gemini_fallback_also_fails():
    """When the unavailable-model fallback also fails, return None."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        _model_not_found_error(),
        Exception("fallback boom"),
    ]

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await ai._generate_text_gemini("prompt")
        assert result is None
        assert mock_client.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_generate_text_gemini_not_configured():
    """Test _generate_text_gemini returns None when no client is configured."""
    with patch("app.services.ai._get_gemini_client", return_value=None):
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
    type(mock_response).text = PropertyMock(return_value="Chat Response")
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        history = [{"role": "user", "content": "hi"}]
        res = await ai.chat_with_gemini("hello", history)
        assert res == "Chat Response"

        # Verify history conversion + config-driven model.
        expected_history = [{"role": "user", "parts": [{"text": "hi"}]}]
        mock_client.chats.create.assert_called_with(
            model=ai.settings.gemini_model, history=expected_history
        )


@pytest.mark.asyncio
async def test_chat_with_gemini_fallback_on_model_unavailable():
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    type(mock_response).text = PropertyMock(return_value="Fallback Chat")
    mock_chat.send_message.return_value = mock_response

    # Primary model 404s (unavailable), fallback succeeds.
    mock_client.chats.create.side_effect = [_model_not_found_error(), mock_chat]

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.chat_with_gemini("hello")
        assert res == "Fallback Chat"
        assert mock_client.chats.create.call_count == 2
        _args, kwargs = mock_client.chats.create.call_args_list[1]
        assert kwargs["model"] == ai.settings.gemini_model_fallback


@pytest.mark.asyncio
async def test_chat_with_gemini_generic_error_no_second_call():
    """A generic chat error must NOT trigger a second (billable) call."""
    mock_client = MagicMock()
    mock_client.chats.create.side_effect = Exception("transient 500")

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.chat_with_gemini("hello")
        assert "Error communicating" in res
        assert mock_client.chats.create.call_count == 1


@pytest.mark.asyncio
async def test_chat_with_gemini_no_fallback_when_same_model():
    mock_client = MagicMock()
    mock_client.chats.create.side_effect = _model_not_found_error()

    with (
        patch("app.services.ai._get_gemini_client", return_value=mock_client),
        patch("app.services.ai.settings.gemini_model", "gemini-x"),
        patch("app.services.ai.settings.gemini_model_fallback", "gemini-x"),
    ):
        res = await ai.chat_with_gemini("hello")
        assert "Error communicating" in res
        assert mock_client.chats.create.call_count == 1


@pytest.mark.asyncio
async def test_chat_with_gemini_fallback_also_fails():
    mock_client = MagicMock()
    mock_client.chats.create.side_effect = [
        _model_not_found_error(),
        Exception("fallback boom"),
    ]

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.chat_with_gemini("hello")
        assert "Error communicating" in res
        assert mock_client.chats.create.call_count == 2


@pytest.mark.asyncio
async def test_no_debug_print_in_ai_module():
    """Regression for #145: no print() statements remain in ai.py."""
    import inspect

    source = inspect.getsource(ai)
    assert "print(" not in source


@pytest.mark.asyncio
async def test_suggest_tags_gemini_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    type(mock_response).text = PropertyMock(return_value='["tag1", "tag2"]')
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        tags = await ai.suggest_tags("Title", "Content")
        assert tags == ["tag1", "tag2"]
        call_args = mock_client.models.generate_content.call_args
        assert "Title" in call_args.kwargs["contents"]


@pytest.mark.asyncio
async def test_suggest_tags_gemini_json_markdown():
    mock_client = MagicMock()
    mock_response = MagicMock()
    type(mock_response).text = PropertyMock(
        return_value='```json\n["tag1", "tag2"]\n```'
    )
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        tags = await ai.suggest_tags("Title", "Content")
        assert tags == ["tag1", "tag2"]


@pytest.mark.asyncio
async def test_suggest_tags_fallback_ollama():
    with (
        patch("app.services.ai._generate_text_gemini", return_value=None),
        patch("app.services.ai.httpx.AsyncClient") as mock_http,
    ):
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
    type(mock_response).text = PropertyMock(
        return_value='{"title": "T", "slug": "s", "summary": "sum", "tags": ["t1"]}'
    )
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        details = await ai.suggest_post_details("Content")
        assert details["title"] == "T"
        assert details["tags"] == ["t1"]


@pytest.mark.asyncio
async def test_suggest_field_gemini_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    type(mock_response).text = PropertyMock(return_value="Suggested Title")
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
        "content": "# Markdown",
    }
    import json

    type(mock_response).text = PropertyMock(return_value=json.dumps(content_json))
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.generate_full_post("Topic")
        assert res["title"] == "Full Post"
        assert res["content"] == "# Markdown"


@pytest.mark.asyncio
async def test_generate_full_post_robust_parsing():
    mock_client = MagicMock()
    mock_response = MagicMock()
    type(mock_response).text = PropertyMock(
        return_value='Sure! Here is the JSON:\n```json\n{"title": "Full Post", "slug": "s", "summary": "sum", "tags": ["t"], "content": "c"}\n```'
    )
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        res = await ai.generate_full_post("Topic")
        assert res["title"] == "Full Post"


@pytest.mark.asyncio
async def test_generate_full_post_fallback_fail():
    with (
        patch("app.services.ai._generate_text_gemini", return_value=None),
        patch("app.services.ai.httpx.AsyncClient") as mock_http,
    ):
        mock_client_instance = AsyncMock()
        mock_http.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.side_effect = Exception("Ollama bad")

        res = await ai.generate_full_post("Topic")
        assert res == {}
