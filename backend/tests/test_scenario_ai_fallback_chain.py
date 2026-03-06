import pytest
from unittest.mock import patch, MagicMock

# Scenario: AI Service Fallback Chain
# 1. Gemini Client Init Failure -> Handled gracefully
# 2. Gemini Generation Failure -> Fallback to 1.5 -> Failure -> Returns None
# 3. Tag Suggestion: Gemini Fails -> Fallback to Ollama -> Success
# 4. Tag Suggestion: Gemini Fails -> Ollama Fails -> Fallback to Regex Extraction


@pytest.mark.asyncio
async def test_ai_scenario_client_init_failure():
    from app.services.ai import _get_gemini_client

    # Mock settings.gemini_api_key
    with patch("app.config.settings.gemini_api_key", "fake_key"):
        with patch("app.services.ai.HAS_GEMINI", True):
            # Mock genai module
            mock_genai = MagicMock()
            mock_genai.Client.side_effect = Exception("Init Fail")

            # Patch sys.modules to inject google.genai
            with patch.dict(
                "sys.modules", {"google": MagicMock(), "google.genai": mock_genai}
            ):
                # Also force-patch the attribute if it was already imported in the module
                with patch("app.services.ai.genai", mock_genai, create=True):
                    client = _get_gemini_client(user_api_key="fake")
                    assert client is None


@pytest.mark.asyncio
async def test_ai_scenario_generation_all_models_fail():
    from app.services.ai import _generate_text_gemini

    mock_client = MagicMock()
    # first call fails, second call fails.
    # Note: generate_content is sync in 2.0 SDK but might be wrapped?
    # Code: response = client.models.generate_content(...)
    mock_client.models.generate_content.side_effect = [
        Exception("2.0 Fail"),
        Exception("1.5 Fail"),
    ]

    with patch("app.services.ai._get_gemini_client", return_value=mock_client):
        result = await _generate_text_gemini("prompt")
        assert result is None


@pytest.mark.asyncio
async def test_ai_scenario_tag_suggestion_ollama_fallback():
    from app.services.ai import suggest_tags
    from unittest.mock import AsyncMock

    with patch("app.services.ai._generate_text_gemini", return_value=None):
        # Correctly mock AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        # json() returns the dict which has "response" key with string content
        mock_response.json.return_value = {"response": '["tag1", "tag2"]'}
        mock_response.raise_for_status = MagicMock()

        # AsyncClient patch
        mock_ac_instance = MagicMock()
        # post must be awaitable
        mock_ac_instance.post = AsyncMock(return_value=mock_response)

        # Async context manager support
        mock_ac_instance.__aenter__.return_value = mock_ac_instance
        mock_ac_instance.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_ac_instance):
            tags = await suggest_tags("title", "content")
            assert tags == ["tag1", "tag2"]


@pytest.mark.asyncio
async def test_ai_scenario_tag_suggestion_regex_fallback():
    from app.services.ai import suggest_tags

    with patch("app.services.ai._generate_text_gemini", return_value=None):
        mock_ac_instance = MagicMock()
        # post raises exception to trigger regex fallback
        mock_ac_instance.post.side_effect = Exception("Ollama Down")
        mock_ac_instance.__aenter__.return_value = mock_ac_instance
        mock_ac_instance.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_ac_instance):
            # Content designed to trigger regex fallback (>5 char lowercase words)
            # Ensure "docker" is among the first 5 words found
            tags = await suggest_tags("title", "python docker kubernetes angular react")
            # tag matching logic validation
            assert "python" in tags
            assert "docker" in tags
