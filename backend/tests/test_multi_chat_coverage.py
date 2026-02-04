import pytest
import json
import asyncio
import uuid
from unittest.mock import MagicMock, patch
from app.services.multi_chat import multi_agent_conversation, AgentConfig


@pytest.mark.asyncio
async def test_multi_agent_conversation_success():
    """Test full success path of multi-agent conversation with mocked CrewAI."""
    agents_config = [
        AgentConfig(id=1, name="Scientist", role="R1", goal="G1", description="D1"),
        AgentConfig(id=2, name="Philosopher", role="R2", goal="G2", description="D2"),
    ]
    topic = "Test Topic"

    # Capture queue via callback mock
    mock_queue_ref = []

    class MockCallbackHandler:
        def __init__(self, queue):
            mock_queue_ref.append(queue)
            self.queue = queue

    class MockProcess:
        sequential = "sequential"
        hierarchical = "hierarchical"

    # Create valid mocks for CrewAI components
    with (
        patch("app.services.multi_chat.ChatOpenAI"),
        patch("app.services.multi_chat.Agent") as MockAgent,
        patch("app.services.multi_chat.Task"),
        patch("app.services.multi_chat.Crew") as MockCrew,
        patch("app.services.multi_chat.Process", MockProcess),
        patch(
            "app.services.multi_chat.StreamingCallbackHandler",
            side_effect=MockCallbackHandler,
        ),
    ):
        # Setup Crew Mock
        mock_crew_instance = MockCrew.return_value

        # When kickoff is called, we want to simulate tokens being pushed to the queue.
        # Since kickoff runs in an executor, we can't easily access the queue instantly inside the test
        # unless we capture it first.
        # But kickoff is called inside a background task.

        # Let's use a side effect for kickoff that pushes to the captured queue
        def kickoff_side_effect():
            # Only push if we successfully captured queue
            if mock_queue_ref:
                q = mock_queue_ref[0]
                # Simulate tokens
                q.put_nowait({"content": "Hello", "agent_name": "Scientist"})
                q.put_nowait({"content": "World", "agent_name": "Philosopher"})

        mock_crew_instance.kickoff.side_effect = kickoff_side_effect

        # Run the generator
        gen = multi_agent_conversation(agents_config, topic)

        chunks = []
        async for chunk in gen:
            chunks.append(json.loads(chunk))

        # Verify Agent creation - we check specific calls or count
        # We expect 2 agents created
        assert MockAgent.call_count == 2

        # Verify call args for first agent
        # We need to verify that 'role', 'name', 'goal', 'backstory' were passed correctly
        call_args = MockAgent.call_args_list[0]
        _, kwargs = call_args
        assert kwargs["name"] == "Scientist"
        assert kwargs["role"] == "R1"
        assert kwargs["goal"] == "G1"
        assert kwargs["backstory"] == "D1"
        # Ensure LLM passed is NOT the generic one, but one created for this agent.
        # We can't strict check the instance easily without more mocking, but we can check it's passed.
        assert "llm" in kwargs

        # Verify Output Content
        # We expect parsed messages. Agent IDs mapped from names.
        # Scientist ID=1, Philosopher ID=2

        # Chunk 1: Hello from Scientist (1)
        # Chunk 2: World from Philosopher (2)
        # Last Chunk: Done

        content_chunks = [c for c in chunks if not c.get("done")]
        done_chunk = chunks[-1]

        assert len(content_chunks) >= 2

        assert content_chunks[0]["agent"] == 1
        assert content_chunks[0]["content"] == "Hello"

        assert content_chunks[1]["agent"] == 2
        assert content_chunks[1]["content"] == "World"

        assert done_chunk["done"] is True
        assert "[Conversation Finished]" in done_chunk["content"]


@pytest.mark.asyncio
async def test_multi_agent_conversation_error():
    """Test error handling during kickoff."""
    agents_config = [AgentConfig(id=1, description="D1", name="A1")]

    class MockProcess:
        sequential = "sequential"
        hierarchical = "hierarchical"

    with (
        patch("app.services.multi_chat.ChatOpenAI"),
        patch("app.services.multi_chat.Agent"),
        patch("app.services.multi_chat.Task"),
        patch("app.services.multi_chat.Crew") as MockCrew,
        patch("app.services.multi_chat.Process", MockProcess),
    ):
        mock_crew = MockCrew.return_value
        mock_crew.kickoff.side_effect = Exception("Crew Crash")

        gen = multi_agent_conversation(agents_config, "Topic")
        chunks = []
        async for chunk in gen:
            chunks.append(json.loads(chunk))

        # Error chunk should be present before [Debate Concluded]
        error_chunks = [
            c for c in chunks if "Error: Crew Crash" in c.get("content", "")
        ]
        assert len(error_chunks) > 0

        last = chunks[-1]
        assert last["done"] is True
        assert "[Conversation Finished]" in last["content"]


@pytest.mark.asyncio
async def test_streaming_callback_handler():
    """Test the callback handler directly for coverage."""
    from app.services.multi_chat import StreamingCallbackHandler

    queue = asyncio.Queue()
    handler = StreamingCallbackHandler(queue)
    handler.current_agent_name = "TestAgent"

    # Test new token
    handler.on_llm_new_token("token")
    item = await queue.get()
    assert item["content"] == "token"
    assert item["agent_name"] == "TestAgent"

    # Test empty token (should not push)
    handler.on_llm_new_token("")
    assert queue.empty()

    # Test on_llm_end (should pass)
    handler.on_llm_end(response=MagicMock(), run_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_multi_agent_consumer_exception():
    """Test exception raised during queue consumption."""
    agents_config = [AgentConfig(id=1, description="D1", name="A1")]

    # We mock asyncio.wait_for to raise an exception when pulling from queue
    # No, we mock queue.get.
    # But queue is created inside the function.
    # We must patch asyncio.Queue to return a mock queue.

    mock_queue = MagicMock()
    mock_queue.get.side_effect = RuntimeError("Queue Error")
    mock_queue.put_nowait = MagicMock()

    class MockProcess:
        sequential = "sequential"
        hierarchical = "hierarchical"

    with (
        patch("asyncio.Queue", return_value=mock_queue),
        patch("app.services.multi_chat.ChatOpenAI"),
        patch("app.services.multi_chat.Agent"),
        patch("app.services.multi_chat.Task"),
        patch("app.services.multi_chat.Crew"),
        patch("app.services.multi_chat.Process", MockProcess),
    ):
        gen = multi_agent_conversation(agents_config, "Topic")
        chunks = []

        # Expect RuntimeError to propagate
        with pytest.raises(RuntimeError, match="Queue Error"):
            async for chunk in gen:
                chunks.append(json.loads(chunk))

        # We can't check chunks after exception usually, as it interrupts flow
        # But we verify the exception was raised.
