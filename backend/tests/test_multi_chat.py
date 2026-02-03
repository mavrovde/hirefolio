import pytest
import json
from unittest.mock import patch
from app.services.multi_chat import multi_agent_conversation, AgentConfig


@pytest.mark.asyncio
async def test_multi_agent_conversation_success():
    """Test successful multi-agent conversation flow."""
    agents = [
        AgentConfig(id=1, description="D1", name="Agent 1"),
        AgentConfig(id=2, description="D2", name="Agent 2"),
        AgentConfig(id=3, description="D3", name="Agent 3"),
    ]
    topic = "Test Topic"

    # Mock chat_with_llm
    # It must be an async generator function
    async def mock_generator(*args, **kwargs):
        yield "Hello "
        yield "World"

    with patch("app.services.multi_chat.chat_with_llm", side_effect=mock_generator):
        # Run conversation
        gen = multi_agent_conversation(agents, topic)

        chunks = []
        async for chunk in gen:
            chunks.append(json.loads(chunk))

        # Verification
        # We expect turns.
        # For agent 1: "Hello", "World", "turn_complete"
        # For agent 2: "Hello", "World", "turn_complete"
        # ... until MAX_TURNS or stopped.
        # But wait, MAX_TURNS is 15. The loop runs many times.
        # Our mock generator returns immediately for each call.

        assert len(chunks) > 0
        first_chunk = chunks[0]
        assert first_chunk["agent"] == 1
        assert first_chunk["content"] == "Hello "

        # Verify round robin
        # chunks will contain:
        # A1 chunks..., {turn_complete: True}
        # A2 chunks..., {turn_complete: True}
        # A3 chunks..., {turn_complete: True}
        # A1 chunks...

        turn_completes = [c for c in chunks if c.get("turn_complete")]
        agents_turns = [c["agent"] for c in turn_completes]

        # Should be sequence 1, 2, 3, 1, 2, 3...
        assert agents_turns[:3] == [1, 2, 3]


@pytest.mark.asyncio
async def test_multi_agent_conversation_empty_agents():
    """Test conversation with no agents returns immediately."""
    gen = multi_agent_conversation([], "Topic")
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    assert len(chunks) == 0


@pytest.mark.asyncio
async def test_multi_agent_conversation_error():
    """Test error handling in conversation."""
    agents = [AgentConfig(id=1, description="D1")]

    with patch(
        "app.services.multi_chat.chat_with_llm", side_effect=Exception("API Error")
    ):
        gen = multi_agent_conversation(agents, "Topic")
        chunks = []
        async for chunk in gen:
            chunks.append(json.loads(chunk))

        last_chunk = chunks[-1]
        assert last_chunk["done"] is True
        assert "Error" in last_chunk["content"]
