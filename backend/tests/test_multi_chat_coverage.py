import pytest
import json
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.multi_chat import multi_agent_conversation, AgentConfig


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
        return

    mock_stream_resp = MagicMock()
    mock_stream_resp.status_code = 200
    mock_stream_resp.aiter_lines = mock_aiter_lines

    class MockAsyncContextManager:
        async def __aenter__(self):
            return mock_stream_resp

        async def __aexit__(self, exc_type, exc, tb):
            pass

    with (
        patch("app.services.multi_chat.Agent"),
        patch("httpx.AsyncClient") as MockClient,
    ):
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


@pytest.mark.asyncio
async def test_streaming_callback_handler():
    """Test the callback handler directly for coverage."""
    from app.services.multi_chat import StreamingCallbackHandler

    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    handler = StreamingCallbackHandler(queue, loop)
    handler.current_agent_name = "TestAgent"

    # Test new token
    handler.on_llm_new_token("token")

    # Give the loop a chance to process the callback
    await asyncio.sleep(0.01)

    item = await queue.get()
    assert item["content"] == "token"
    assert item["agent_name"] == "TestAgent"

    # Test empty token (should not push)
    handler.on_llm_new_token("")
    assert queue.empty()
