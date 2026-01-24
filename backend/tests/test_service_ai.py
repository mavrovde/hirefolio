import pytest
import respx
from httpx import Response
from app.services.ai import suggest_tags
from app.config import settings


@pytest.mark.asyncio
async def test_suggest_tags_valid_json():
    """Test AI service with valid JSON response from Ollama."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": '["angular", "typescript", "web-dev"]'}
            )
        )

        tags = await suggest_tags("Title", "Content")
        assert tags == ["angular", "typescript", "web-dev"]


@pytest.mark.asyncio
async def test_suggest_tags_wrapped_json():
    """Test AI service with JSON wrapped in a dict object."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200, json={"response": '{"tags": ["python", "fastapi"]}'}
            )
        )

        tags = await suggest_tags("Title", "Content")
        assert tags == ["python", "fastapi"]


@pytest.mark.asyncio
async def test_suggest_tags_fallback_text():
    """Test AI service with plain text response (fallback regex)."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        # Malformed JSON or just text
        respx_mock.post("/api/generate").mock(
            return_value=Response(
                200,
                json={"response": "Here are tags: rust, performance, memory-safety"},
            )
        )

        tags = await suggest_tags("Title", "Content")
        # Regex should split by words and filter generic short ones
        assert "rust" in tags
        assert "performance" in tags
        # memory-safety might be split or kept depending on regex \b\w+\b
        # \w includes alphanumeric and underscore, not hyphen usually.
        # So "memory", "safety".
        assert "memory" in tags


@pytest.mark.asyncio
async def test_suggest_tags_http_error():
    """Test AI service with HTTP error."""
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        respx_mock.post("/api/generate").mock(return_value=Response(500))

        tags = await suggest_tags("Title", "Content")
        assert tags == []


@pytest.mark.asyncio
async def test_suggest_tags_connection_error():
    """Test AI service with connection failure."""
    # Mocking httpx ConnectError is harder with respx sometimes,
    # but we can rely on route side_effect
    with respx.mock(base_url=settings.ollama_url) as respx_mock:
        import httpx

        respx_mock.post("/api/generate").mock(
            side_effect=httpx.ConnectError("Connection refused", request=None)
        )

        tags = await suggest_tags("Title", "Content")
        assert tags == []
