from app.config import settings
import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_gemini_chat_endpoint_error_handling(client: AsyncClient):
    """When chat_with_gemini raises, the endpoint returns 500 with a generic detail.

    Covers the except-block in gemini_chat_endpoint (lines 56-60).
    """
    with patch(
        "app.services.ai.chat_with_gemini", side_effect=Exception("Gemini boom")
    ) as mock_chat:
        response = await client.post(
            f"{settings.api_prefix}/ai/gemini-chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Error communicating with AI service"}
    mock_chat.assert_called_once()
