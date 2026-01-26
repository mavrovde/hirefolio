import pytest
from unittest.mock import AsyncMock, patch
import httpx

from app.services.embeddings import get_embedding


@pytest.mark.asyncio
async def test_get_embedding_success():
    """Test successful embedding generation."""
    mock_response = {"embedding": [0.1] * 768}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200, json=lambda: mock_response, raise_for_status=lambda: None
        )

        result = await get_embedding("test text")

        assert result is not None
        assert len(result) == 768
        assert all(isinstance(x, float) for x in result)


@pytest.mark.asyncio
async def test_get_embedding_http_error():
    """Test handling of HTTP errors."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.HTTPError("Connection failed")

        result = await get_embedding("test text")

        assert result is None


@pytest.mark.asyncio
async def test_get_embedding_connection_error():
    """Test handling of connection errors."""


@pytest.mark.asyncio
async def test_get_embedding_logging():
    """Test that errors are logged in get_embedding."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.HTTPError("Log this error")
        with patch("app.services.embeddings.logger") as mock_logger:
            result = await get_embedding("test")
            assert result is None
            mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_get_embedding_timeout():
    """Test handling of timeout errors."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        result = await get_embedding("test text")

        assert result is None


@pytest.mark.asyncio
async def test_get_embedding_invalid_response():
    """Test handling of invalid response format."""
    mock_response = {"invalid_key": "no embedding here"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200, json=lambda: mock_response, raise_for_status=lambda: None
        )

        result = await get_embedding("test text")

        assert result is None
