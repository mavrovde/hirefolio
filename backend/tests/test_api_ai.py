from app.config import settings
import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
@patch("app.api.ai.chat_with_llm")
async def test_chat_endpoint(mock_chat_service, client: AsyncClient):
    # Mock the generator to yield data immediately
    async def mock_generator(messages):
        yield "AI Response"

    mock_chat_service.side_effect = mock_generator

    response = await client.post(
        f"{settings.api_prefix}/ai/chat", json={"messages": [{"role": "user", "content": "hello"}]}
    )

    assert response.status_code == 200
    assert "AI Response" in response.text


@pytest.mark.asyncio
@patch("app.api.ai.chat_with_llm")
async def test_generate_name_success(mock_chat_service, client: AsyncClient):
    async def mock_generator(messages):
        yield "Creative Agent Name"

    mock_chat_service.side_effect = mock_generator

    response = await client.post(
        f"{settings.api_prefix}/ai/generate-name", json={"description": "A skeptic and philosopher"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Creative Agent Name"


@pytest.mark.asyncio
@patch("app.api.ai.chat_with_llm")
async def test_generate_name_exception_fallback(mock_chat_service, client: AsyncClient):
    # Simulate an error in the LLM service
    mock_chat_service.side_effect = Exception("LLM Error")

    response = await client.post(
        f"{settings.api_prefix}/ai/generate-name", json={"description": "trigger error"}
    )

    assert response.status_code == 200
    # Should fallback to "Agent" as per line 58 in app{settings.api_prefix}/ai.py
    assert response.json()["name"] == "Agent"
