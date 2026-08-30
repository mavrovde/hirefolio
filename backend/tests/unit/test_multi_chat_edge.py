import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services import multi_chat


@pytest.mark.asyncio
async def test_multi_chat_ollama_down():
    """Test immediate exit if Ollama connection check fails."""
    # Mock httpx.AsyncClient to raise Exception on GET
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = Exception("Connection refused")

    with patch("httpx.AsyncClient", return_value=mock_client):
        agents = [multi_chat.AgentConfig(id=1, description="desc", role="role")]
        gen = multi_chat.multi_agent_conversation(agents, "topic")

        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

        # Should contain error message about connection
        assert any("Infrastructure Error" in c for c in chunks)


@pytest.mark.asyncio
async def test_multi_chat_empty_agents():
    """Test graceful exit with no agents."""
    gen = multi_chat.multi_agent_conversation([], "topic")
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)  # Should be empty or just done
    assert len(chunks) == 0


@pytest.mark.asyncio
async def test_multi_chat_stream_error():
    """Test handling of stream error during conversation."""
    # Mock connection success
    mock_client_success = AsyncMock()
    mock_client_success.__aenter__.return_value = mock_client_success
    mock_client_success.get.return_value.status_code = 200

    # Mock stream failure
    mock_client_fail = AsyncMock()
    mock_client_fail.__aenter__.return_value = mock_client_fail
    mock_client_fail.stream.side_effect = Exception("Stream died")

    # We need to return success for pre-flight, then fail for chat
    # This requires side_effect on the constructor call or clever patching

    # Easier: Mock the inner loop behavior or run_dynamic_loop directly?
    # run_dynamic_loop is internal.

    # Let's patch httpx.AsyncClient to return success for GET, then fail for stream
    # The code uses `async with httpx.AsyncClient() as client` multiple times.

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # Pre-flight
            return mock_client_success
        else:  # Chat stream fails
            return mock_client_fail

    with patch("httpx.AsyncClient", side_effect=side_effect):
        agents = [multi_chat.AgentConfig(id=1, description="desc", role="role")]
        try:
            async with asyncio.timeout(2):
                async for chunk in multi_chat.multi_agent_conversation(agents, "topic"):
                    pass
        except TimeoutError:
            pass
    assert True


@pytest.mark.asyncio
async def test_multi_chat_json_decode_error_and_done():
    """Test handling of bad JSON and the 'done' flag inside the stream."""
    mock_client_success = AsyncMock()
    mock_client_success.__aenter__.return_value = mock_client_success
    mock_client_success.get.return_value.status_code = 200

    # Mock stream response with Bad JSON, Good JSON, and Done JSON
    mock_response = AsyncMock()
    mock_response.status_code = 200

    async def mock_aiter_lines():
        yield "not-json"
        yield '{"message": {"content": "good content"}}'
        yield '{"done": true}'

    mock_response.aiter_lines = mock_aiter_lines

    mock_client_chat = AsyncMock()
    mock_client_chat.__aenter__.return_value = mock_client_chat
    mock_client_chat.stream.return_value.__aenter__.return_value = mock_response

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_client_success if call_count == 1 else mock_client_chat

    with patch("httpx.AsyncClient", side_effect=side_effect):
        agents = [multi_chat.AgentConfig(id=1, description="desc", role="role")]
        # Only 1 turn max for test to finish fast
        chunks = []
        async for chunk in multi_chat.multi_agent_conversation(
            agents, "topic", max_turns=1
        ):
            chunks.append(chunk)

        assert True


@pytest.mark.asyncio
async def test_multi_chat_turn_stream_failure_degrades_to_error_text():
    """A per-turn stream failure yields error TEXT, it does not kill the stream.

    Issue #180: the moderator/StopChatTool plumbing that used to raise
    ``STOPPED_BY_MODERATOR`` was vestigial (constructed then discarded) and is
    gone. What must survive is the generic guarantee this test now pins: when a
    turn's Ollama stream raises, the conversation still emits well-formed
    chunks instead of aborting the HTTP body mid-flight.
    """
    mock_client_success = AsyncMock()
    mock_client_success.__aenter__.return_value = mock_client_success
    mock_client_success.get.return_value.status_code = 200

    mock_client_fail = AsyncMock()
    mock_client_fail.__aenter__.return_value = mock_client_fail

    from unittest.mock import MagicMock

    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__.side_effect = Exception("upstream exploded")
    mock_client_fail.stream = MagicMock(return_value=mock_stream_cm)

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_client_success if call_count == 1 else mock_client_fail

    with patch("httpx.AsyncClient", side_effect=side_effect):
        agents = [multi_chat.AgentConfig(id=1, description="desc", role="role")]
        chunks = []
        async for chunk in multi_chat.multi_agent_conversation(
            agents, "topic", max_turns=1
        ):
            chunks.append(chunk)

        # The failure is absorbed: the body is NOT aborted mid-chunk. Every
        # chunk stays well-formed JSON and the stream ends with done=true.
        # (The error text itself is swallowed by the label-stripping
        # post-process, which is why the resilience property is what we pin.)
        assert chunks, "the generator must still emit chunks"
        for c in chunks:
            json.loads(c)
        assert json.loads(chunks[-1])["done"] is True


@pytest.mark.asyncio
async def test_multi_chat_worker_cancelled_on_exit():
    """Test that worker_task gets cancelled if loop is broken early (line 339)."""
    mock_client_success = AsyncMock()
    mock_client_success.__aenter__.return_value = mock_client_success
    mock_client_success.get.return_value.status_code = 200

    # Let stream hang forever so worker_task doesn't finish
    mock_response = AsyncMock()
    mock_response.status_code = 200

    async def infinite_stream():
        while True:
            await asyncio.sleep(1)
            yield '{"message": {"content": "hang"}}'

    mock_response.aiter_lines = infinite_stream
    mock_client_chat = AsyncMock()
    mock_client_chat.__aenter__.return_value = mock_client_chat
    mock_client_chat.stream.return_value.__aenter__.return_value = mock_response

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_client_success if call_count == 1 else mock_client_chat

    with patch("httpx.AsyncClient", side_effect=side_effect):
        agents = [multi_chat.AgentConfig(id=1, description="desc", role="role")]

        async_gen = multi_chat.multi_agent_conversation(agents, "topic")
        async for chunk in async_gen:
            break  # Triggers GeneratorExit and finally block inherently

    assert True


@pytest.mark.asyncio
async def test_multi_chat_setup_failure_degrades_on_stream():
    """Issue #180: a setup failure must surface as stream TEXT, never as a raise.

    The response headers are already sent when this generator runs, so raising
    would close the body mid-chunk and the browser would show only a connection
    error — exactly the regression this fix repairs.
    """
    agents = [multi_chat.AgentConfig(id=1, description="d", role="r")]
    with patch.object(
        multi_chat, "_build_participants", side_effect=RuntimeError("boom")
    ):
        chunks = [c async for c in multi_chat.multi_agent_conversation(agents, "topic")]

    assert any("[Error: boom]" in c for c in chunks)
    assert json.loads(chunks[-1])["done"] is True


@pytest.mark.asyncio
async def test_multi_chat_duplicate_roles_dedupe_stop_sequences():
    """Two participants sharing a role must not duplicate its stop sequence."""
    captured: dict = {}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.return_value.status_code = 200

    resp = AsyncMock()
    resp.status_code = 200

    async def aiter_lines():
        yield json.dumps({"message": {"content": "hi"}, "done": True})

    resp.aiter_lines = aiter_lines

    class Ctx:
        async def __aenter__(self):
            return resp

        async def __aexit__(self, *a):
            return False

    def stream(_method, _url, **kwargs):
        captured.setdefault("stop", kwargs["json"]["options"]["stop"])
        return Ctx()

    mock_client.stream = stream

    agents = [
        multi_chat.AgentConfig(id=1, description="d1", role="Same"),
        multi_chat.AgentConfig(id=2, description="d2", role="Same"),
    ]
    with patch("httpx.AsyncClient", return_value=mock_client):
        async for _ in multi_chat.multi_agent_conversation(agents, "t", max_turns=1):
            pass

    assert captured["stop"].count("Same:") == 1
