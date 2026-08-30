from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
@patch("app.api.ai.chat_with_llm")
async def test_chat_endpoint(mock_chat_service, client: AsyncClient):
    # Mock the generator to yield data immediately
    async def mock_generator(messages):
        yield "AI Response"

    mock_chat_service.side_effect = mock_generator

    response = await client.post(
        f"{settings.api_prefix}/ai/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
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
        f"{settings.api_prefix}/ai/generate-name",
        json={"description": "A skeptic and philosopher"},
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


@pytest.mark.asyncio
@patch("app.api.ai.chat_with_llm")
async def test_generate_name_failure_is_logged(
    mock_chat_service, client: AsyncClient, caplog
):
    """#191: the fallback is fine, the SILENCE was not.

    A real failure (model down, timeout, malformed reply) used to be
    indistinguishable from a legitimate default — nothing reached the logs, so an
    operator seeing every agent named "Agent" had no signal at all (rule 1).
    """
    import logging

    mock_chat_service.side_effect = Exception("LLM exploded")

    with caplog.at_level(logging.ERROR):
        response = await client.post(
            f"{settings.api_prefix}/ai/generate-name", json={"description": "boom"}
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Agent"
    assert any("Agent-name generation failed" in r.message for r in caplog.records), (
        "the failure must be logged, not swallowed"
    )
    # The exception itself must be in the log record, not only the message.
    assert any(r.exc_info for r in caplog.records)


@pytest.mark.asyncio
async def test_gemini_chat_endpoint(client: AsyncClient):
    with patch(
        "app.services.ai.chat_with_gemini", return_value="Chat Response"
    ) as mock_chat:
        response = await client.post(
            f"{settings.api_prefix}/ai/gemini-chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
        assert response.status_code == 200
        assert response.json() == {"response": "Chat Response"}

        # Verify call arguments
        # history should be empty list (slice [:-1] of 1 item is empty)
        # last message "Hello"
        # api_key should be None (default for mock user)
        mock_chat.assert_called_with("Hello", [], None)


@pytest.mark.asyncio
async def test_gemini_chat_endpoint_with_history(client: AsyncClient):
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "model", "content": "Hello"},
        {"role": "user", "content": "How are you?"},
    ]
    with patch(
        "app.services.ai.chat_with_gemini", return_value="I am good"
    ) as mock_chat:
        response = await client.post(
            f"{settings.api_prefix}/ai/gemini-chat", json={"messages": messages}
        )
        assert response.status_code == 200
        assert response.json() == {"response": "I am good"}

        mock_chat.assert_called_with(
            "How are you?",
            [{"role": "user", "content": "Hi"}, {"role": "model", "content": "Hello"}],
            None,
        )
