import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.chat import chat_with_llm

# Scenario: Chat stream success
# Expected: Yield content chunks


@pytest.mark.asyncio
async def test_scenario_chat_stream_success():
    messages = [{"role": "user", "content": "hi"}]

    # Mock httpx response stream
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def aiter_lines():
        yield json.dumps({"message": {"content": "Hello"}, "done": False})
        yield json.dumps({"message": {"content": " World"}, "done": True})

    mock_response.aiter_lines = aiter_lines

    mock_client = MagicMock()
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__.return_value = mock_response
    mock_stream_ctx.__aexit__.return_value = None

    mock_client.stream.return_value = mock_stream_ctx
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        gen = chat_with_llm(messages)
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

        assert "".join(chunks) == "Hello World"


# Scenario: JSON Decode Error
# Expected: Warning logged, continue to next line


@pytest.mark.asyncio
async def test_scenario_chat_stream_json_error():
    messages = [{"role": "user", "content": "hi"}]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    async def aiter_lines():
        yield "invalid json"
        yield json.dumps({"message": {"content": "Recovered"}, "done": True})

    mock_response.aiter_lines = aiter_lines

    mock_client = MagicMock()
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__.return_value = mock_response
    mock_stream_ctx.__aexit__.return_value = None

    mock_client.stream.return_value = mock_stream_ctx
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        gen = chat_with_llm(messages)
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

        assert "Recovered" in chunks


# Scenario: Connection Error
# Expected: Yield System Error message


@pytest.mark.asyncio
async def test_scenario_chat_stream_connection_error():
    messages = [{"role": "user", "content": "hi"}]

    mock_client = MagicMock()
    mock_client.__aenter__.side_effect = Exception("Connection Failed")

    with patch("httpx.AsyncClient", return_value=mock_client):
        gen = chat_with_llm(messages)
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

        assert any("System Error" in c for c in chunks)
