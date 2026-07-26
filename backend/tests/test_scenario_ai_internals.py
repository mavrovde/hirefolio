import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai import generate_full_post


@pytest.mark.asyncio
async def test_ai_generate_full_post_http_error():
    """Test generate_full_post returns empty dict on HTTP error in fallback."""
    # Force Gemini to fail (return None)
    with patch(
        "app.services.ai._generate_text_gemini", new_callable=AsyncMock
    ) as mock_gemini:
        mock_gemini.return_value = None

        # Force Ollama HTTP error
        with patch("httpx.AsyncClient.post", side_effect=Exception("Ollama Error")):
            result = await generate_full_post("Topic")
            assert result == {}


@pytest.mark.asyncio
async def test_ai_generate_full_post_json_fallback_regex():
    """Test generate_full_post falls back to regex parsing if JSON format is slightly off."""
    # Force Gemini fail
    with patch(
        "app.services.ai._generate_text_gemini", new_callable=AsyncMock
    ) as mock_gemini:
        mock_gemini.return_value = None

        # Ollama returns "markdown json" without braces at ends maybe?
        # Actually code checks for { and }.
        # If we return text with markdown blocks:

        json.dumps(
            {
                "title": "Regex Title",
                "slug": "regex-slug",
                "summary": "Sum",
                "tags": ["t1"],
                "content": "Cont",
            }
        )
        # Wrap in quotes or something that breaks the first find('{') check?
        # Code: start_idx = response_text.find("{")
        # If we provide text with NO braces, it goes to `else` block (regex fallback)

        # Code:
        # cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text).strip()
        # post_data = json.loads(cleaned_text)

        # So we need to provide something that `find('{')` misses?
        # `find` returns -1 if not found.
        # So providing just JSON without surrounding text should be found.
        # Providing NO braces: start_idx = -1.
        # Then regex strips markdown. Then json.loads.

        # So if we provide ```json {"a":1} ``` WITHOUT external braces? No, that has braces.

        # The logic is:
        # if start_idx != -1 ... : extract substring
        # else: regex strip markdown -> json.loads

        # So to test the ELSE block, we need input that has NO `{` or `}` but is somehow valid JSON after regex?
        # Only valid JSON scalars (string, int) or list `[]` would pass `json.loads`?
        # But `post_data` is expected to be dict later.

        # If we return ` "some string" ` -> json.loads -> string. Then validation fails.
        # This covers the line 412-413 path!

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": '"Just a string"'}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await generate_full_post("Topic")
            # Should fail validation and return empty
            assert result == {}


@pytest.mark.asyncio
async def test_ai_generate_full_post_missing_keys():
    """Test generate_full_post returns empty dict if required keys are missing."""
    # Mock Gemini success but invalid structure
    with patch(
        "app.services.ai._generate_text_gemini", new_callable=AsyncMock
    ) as mock_gemini:
        mock_gemini.return_value = (
            '{"title": "Missing Slug"}'  # Valid JSON, missing keys
        )

        result = await generate_full_post("Topic")
        assert result == {}


@pytest.mark.asyncio
async def test_ai_import_error_simulation():
    """Simulate ImportError for google.genai."""
    # This is hard to test dynamically as module is already imported.
    # We can patch HAS_GEMINI flag if `_get_gemini_client` uses it.

    with patch("app.services.ai.HAS_GEMINI", False):
        # Call private method to verify it handles False
        from app.services.ai import _get_gemini_client

        assert _get_gemini_client() is None
