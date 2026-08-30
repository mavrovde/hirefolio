import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.multi_chat import AgentConfig, multi_agent_conversation

# Scenario: Multi-agent conversation flow
# 1. Connection check passes.
# 2. Agents generated.
# 3. Conversation loop runs and yields tokens.
# 4. Graceful shutdown.


@pytest.mark.asyncio
async def test_scenario_multi_chat_flow():
    # Config
    agents = [
        AgentConfig(id=1, description="Backstory 1", role="Role 1", name="Agent 1"),
        AgentConfig(id=2, description="Backstory 2", role="Role 2", name="Agent 2"),
    ]

    # Mock httpx for connection check and chat calls
    mock_response_check = MagicMock()
    mock_response_check.status_code = 200

    mock_response_chat = MagicMock()
    mock_response_chat.status_code = 200

    # Stream response lines helper
    async def aiter_lines():
        # Yield valid JSON lines simulating Ollama stream
        yield json.dumps({"message": {"content": "Hello "}, "done": False})
        yield json.dumps({"message": {"content": "World"}, "done": False})
        yield json.dumps({"done": True})

    mock_response_chat.aiter_lines = aiter_lines

    mock_client = MagicMock()

    # Handle GET (connection check) and POST (chat)
    async def side_effect_client(*args, **kwargs):
        # Return context manager
        return mock_client

    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    # Differentiate responses based on method/url?
    # Or just return different things based on call order?
    # Simple approach: mock methods
    mock_client.get = AsyncMock(return_value=mock_response_check)

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__.return_value = mock_response_chat
    mock_stream_ctx.__aexit__.return_value = None

    mock_client.stream.return_value = mock_stream_ctx

    # Patch Deps
    with patch("httpx.AsyncClient", return_value=mock_client):
        # Execute generator
        gen = multi_agent_conversation(agents, "Topic", max_turns=2)

        results = []
        async for chunk in gen:
            results.append(json.loads(chunk))

        # Assertions
        assert len(results) > 0
        # Expect conversation finished message at end
        assert results[-1]["content"] == "[Conversation Finished]"

        # Expect some content
        content_items = [r for r in results if r.get("content") == "Hello "]
        assert len(content_items) > 0


# Scenario: Ollama Connection Failure
# Expected: Yield error message and return


@pytest.mark.asyncio
async def test_scenario_multi_chat_connection_fail():
    agents = [AgentConfig(id=1, description="desc", role="role", name="name")]

    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    # Simulate connection error
    mock_client.get = AsyncMock(side_effect=Exception("Connection Refused"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        gen = multi_agent_conversation(agents, "Topic")
        results = []
        async for chunk in gen:
            results.append(json.loads(chunk))

        assert any("Infrastructure Error" in r["content"] for r in results)
