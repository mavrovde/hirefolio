import pytest
import json
from unittest.mock import patch
from app.services.multi_chat import multi_agent_conversation, AgentConfig


@pytest.mark.asyncio
async def test_multi_agent_conversation_success_path():
    """Test full success path of multi-agent conversation with prefix stripping."""
    agents = [
        AgentConfig(id=1, description="D1", name="Agent1", role="R1", goal="G1"),
        AgentConfig(id=2, description="D2", name="Agent2", role="R2", goal="G2"),
    ]
    topic = "AI Ethics"

    # Mock chat_with_llm to yield specific responses > 40 chars
    async def mock_chat_gen(messages, stop_sequences=None):
        is_agent1 = any(
            msg["role"] == "system" and "Agent1" in msg["content"] for msg in messages
        )
        if is_agent1:
            yield "Agent1: "
            # Yield lot of text to exceed 40 char buffer
            yield "This is a very long response that will definitely exceed the forty character buffer threshold for prefix stripping logic coverage."
            yield " Extra chunk to cover post-stripping lines."
        else:
            yield "Agent2: I actually agree with the previous statement completely and utterly."

    with patch("app.services.multi_chat.chat_with_llm", side_effect=mock_chat_gen):
        with patch("app.services.multi_chat.MAX_TURNS", 2):
            gen = multi_agent_conversation(agents, topic)
            chunks = []
            async for chunk in gen:
                data = json.loads(chunk)
                chunks.append(data)

            # Check content
            contents = "".join([c["content"] for c in chunks if "content" in c])
            assert "threshold" in contents or "Ethical AI" in contents
            assert "agree" in contents

            # Check markers
            assert any(c.get("turn_complete") for c in chunks)
            assert chunks[-1]["done"] is True
            assert "[Debate Concluded]" in chunks[-1]["content"]


@pytest.mark.asyncio
async def test_multi_agent_conversation_time_limit():
    """Test time limit reached."""
    agents = [AgentConfig(id=1, description="D1")]

    # Needs more values to satisfy the loop if it doesn't break immediately
    with patch(
        "app.services.multi_chat.time.time", side_effect=[100, 1000, 2000, 3000, 4000]
    ):
        with patch("app.services.multi_chat.MAX_CONVERSATION_DURATION", 10):
            gen = multi_agent_conversation(agents, "Topic")
            chunks = []
            async for chunk in gen:
                chunks.append(json.loads(chunk))

            assert any(
                "[Limit reached]" in c["content"] for c in chunks if "content" in c
            )
            assert chunks[-1]["done"] is True


@pytest.mark.asyncio
async def test_multi_agent_conversation_short_response():
    """Test path where prefix is never stripped because response is too short."""
    agents = [AgentConfig(id=1, description="D1", name="S")]

    async def mock_short_gen(messages, stop_sequences=None):
        yield "Hi."

    with patch("app.services.multi_chat.chat_with_llm", side_effect=mock_short_gen):
        with patch("app.services.multi_chat.MAX_TURNS", 1):
            gen = multi_agent_conversation(agents, "T")
            chunks = []
            async for chunk in gen:
                chunks.append(json.loads(chunk))
            assert "Hi." in chunks[0]["content"]


@pytest.mark.asyncio
async def test_multi_agent_conversation_exception():
    """Test exception handling."""
    agents = [AgentConfig(id=1, description="D1")]

    with patch(
        "app.services.multi_chat.chat_with_llm",
        side_effect=RuntimeError("Runtime Error"),
    ):
        gen = multi_agent_conversation(agents, "Topic")
        chunks = []
        async for chunk in gen:
            chunks.append(json.loads(chunk))

        assert chunks[-1]["done"] is True
        assert "Runtime Error" in chunks[-1]["content"]


@pytest.mark.asyncio
async def test_multi_agent_conversation_no_agents():
    """Test with empty agents list."""
    gen = multi_agent_conversation([], "Topic")
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    assert len(chunks) == 0
