import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.multi_chat import (
    AgentConfig,
    ChatMessage,
    Participant,
    _build_participants,
    _final_chunk,
    _stream_chunk,
    multi_agent_conversation,
)


@pytest.mark.asyncio
async def test_multi_agent_conversation_success():
    """Test full success path of multi-agent conversation with mocked httpx and Ollama."""
    agents_config = [
        AgentConfig(
            id=1, name="Scientist", role="Scientist", goal="G1", description="D1"
        ),
        AgentConfig(
            id=2, name="Philosopher", role="Philosopher", goal="G2", description="D2"
        ),
    ]
    topic = "Test Topic"

    # Mock responses for Ollama tags and dynamic chat stream
    mock_tags_resp = MagicMock()
    mock_tags_resp.status_code = 200

    # Mock the aiter_lines for the chat stream
    # Each line is a JSON chunk
    mock_lines = [
        json.dumps({"message": {"content": "Hello world"}, "done": False}),
        json.dumps({"message": {"content": " from agent"}, "done": True}),
    ]

    async def mock_aiter_lines():
        for line in mock_lines:
            yield line

    mock_stream_resp = MagicMock()
    mock_stream_resp.status_code = 200
    mock_stream_resp.aiter_lines = mock_aiter_lines

    class MockAsyncContextManager:
        async def __aenter__(self):
            return mock_stream_resp

        async def __aexit__(self, exc_type, exc, tb):
            pass

    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = MockClient.return_value
        mock_client_instance.get = AsyncMock(return_value=mock_tags_resp)
        mock_client_instance.stream.return_value = MockAsyncContextManager()

        # Run the generator with a small max_turns for testing
        gen = multi_agent_conversation(agents_config, topic, max_turns=2)

        chunks = []
        async for chunk in gen:
            chunks.append(json.loads(chunk))

        assert len(chunks) > 0
        # The first chunk should be from Scientist (Agent ID 1)
        # However, the direct loop puts system messages first sometimes
        agent_msgs = [c for c in chunks if c.get("agent") is not None]
        assert len(agent_msgs) > 0

        # Verify done chunk exists
        done_chunks = [c for c in chunks if c.get("done") is True]
        assert len(done_chunks) > 0


def test_build_participants_maps_roles_and_defaults():
    """Issue #180: participants are plain data — no agent framework objects."""
    cfgs = [
        AgentConfig(id=1, name="Sci", role="Scientist", goal="G1", description="D1"),
        AgentConfig(id=2, description="D2"),  # role/goal fall back to defaults
    ]
    participants, id_map = _build_participants(cfgs)
    assert [p.role for p in participants] == ["Scientist", "Participant"]
    assert participants[1].goal == "Participate deeply in the discussion."
    assert participants[1].backstory == "D2"
    assert id_map == {"Scientist": 1, "Participant": 2}
    assert isinstance(participants[0], Participant)


def test_stream_and_final_chunk_shapes():
    chunk = json.loads(_stream_chunk(3, "hi", turn_complete=True))
    assert chunk == {"agent": 3, "content": "hi", "done": False, "turn_complete": True}
    assert _stream_chunk(3, "hi").endswith("\n")
    final = json.loads(_final_chunk())
    assert final["done"] is True and final["agent"] == 0


@pytest.mark.asyncio
async def test_multi_chat_internals():
    """Test internal classes and edge cases of multi_chat."""
    # 1. ChatMessage.to_string
    # from app.services.multi_chat import ChatMessage
    # It is already imported
    msg = ChatMessage(agent_name="TestAgent", content="Hello")
    assert msg.to_string() == "TestAgent: Hello"

    # 2. Empty config
    gen = multi_agent_conversation([], "Topic")
    # Async generator returning immediately raises StopAsyncIteration on first next()
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()
