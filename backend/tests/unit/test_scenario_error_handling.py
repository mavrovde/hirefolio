"""
Tests for error handling and edge cases across services.

Covers uncovered error paths in:
- app.services.chat (JSONDecodeError, empty content, stream errors)
- app.services.multi_chat (infrastructure errors, empty agents)
"""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import chat, multi_chat


def _make_stream_mock(lines):
    """Helper: create a mock httpx client whose .stream() yields the given lines."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    async def aiter_lines():
        for line in lines:
            yield line

    mock_response.aiter_lines = aiter_lines

    @asynccontextmanager
    async def fake_stream(*args, **kwargs):
        yield mock_response

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.stream = fake_stream
    return mock_client


# --- Chat Service Error Handling ---


@pytest.mark.asyncio
async def test_chat_stream_json_decode_error():
    """chat_with_llm should skip malformed JSON lines and continue streaming."""
    lines = [
        "not valid json",
        json.dumps({"message": {"content": "OK"}, "done": False}),
        json.dumps({"done": True}),
    ]
    mock_client = _make_stream_mock(lines)

    with patch("httpx.AsyncClient", return_value=mock_client):
        chunks = []
        async for chunk in chat.chat_with_llm([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)

        assert "OK" in chunks


@pytest.mark.asyncio
async def test_chat_stream_empty_content_skipped():
    """chat_with_llm should not yield empty content chunks."""
    lines = [
        json.dumps({"message": {"content": ""}, "done": False}),
        json.dumps({"message": {"content": "Real"}, "done": False}),
        json.dumps({"done": True}),
    ]
    mock_client = _make_stream_mock(lines)

    with patch("httpx.AsyncClient", return_value=mock_client):
        chunks = []
        async for chunk in chat.chat_with_llm([]):
            chunks.append(chunk)

        assert chunks == ["Real"]


@pytest.mark.asyncio
async def test_chat_stream_connection_error():
    """chat_with_llm should yield system error on connection failure."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client

    @asynccontextmanager
    async def fail_stream(*args, **kwargs):
        raise Exception("Connection refused")
        yield  # pragma: no cover

    mock_client.stream = fail_stream

    with patch("httpx.AsyncClient", return_value=mock_client):
        chunks = []
        async for chunk in chat.chat_with_llm([]):
            chunks.append(chunk)

        assert any("System Error" in c for c in chunks)


# --- Multi Chat Error Handling ---


@pytest.mark.asyncio
async def test_multi_chat_infrastructure_error():
    """multi_agent_conversation should yield error when Ollama is unreachable."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = Exception("Connection refused")

    with patch("httpx.AsyncClient", return_value=mock_client):
        agents = [multi_chat.AgentConfig(id=1, description="desc", role="role")]
        chunks = []
        async for chunk in multi_chat.multi_agent_conversation(agents, "topic"):
            chunks.append(chunk)

        assert any("Infrastructure Error" in c for c in chunks)


@pytest.mark.asyncio
async def test_multi_chat_with_no_agents():
    """multi_agent_conversation should handle empty agent list gracefully."""
    chunks = []
    async for chunk in multi_chat.multi_agent_conversation([], "topic"):
        chunks.append(chunk)

    assert len(chunks) == 0
