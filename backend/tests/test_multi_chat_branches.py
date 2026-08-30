"""Edge-case coverage for app/services/multi_chat.py."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.multi_chat import (
    AgentConfig,
    ChatMessage,
    multi_agent_conversation,
)


def test_chat_message_to_string():
    """Line 49: ChatMessage.to_string formatting."""
    msg = ChatMessage(agent_name="Bob", content="hi")
    assert msg.to_string() == "Bob: hi"


@pytest.mark.asyncio
async def test_multi_agent_empty_config():
    """Line 69: empty agents_config -> generator yields nothing (returns immediately)."""
    gen = multi_agent_conversation([], "topic")
    chunks = [c async for c in gen]
    assert chunks == []


def _make_stream_resp(lines, status_code=200):
    async def aiter_lines():
        for line in lines:
            yield line

    resp = MagicMock()
    resp.status_code = status_code
    resp.aiter_lines = aiter_lines
    return resp


def _make_client_factory(stream_resp, tags_status=200, stream_factory=None):
    """Return a callable to patch httpx.AsyncClient producing a client whose
    `async with httpx.AsyncClient() as client` yields a mock supporting
    `client.get(...)` (awaitable) and `client.stream(...)` (async CM).

    Pass either a single ``stream_resp`` (reused each turn) or a
    ``stream_factory`` callable returning a fresh response per turn.
    """

    tags_resp = MagicMock()
    tags_resp.status_code = tags_status

    def make_stream_cm(*a, **k):
        resp = stream_factory() if stream_factory is not None else stream_resp

        class StreamCM:
            async def __aenter__(self):
                return resp

            async def __aexit__(self, *a):
                return False

        return StreamCM()

    class ClientCM:
        async def get(self, *a, **k):
            return tags_resp

        def stream(self, *a, **k):
            return make_stream_cm()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    def factory(*a, **k):
        return ClientCM()

    return factory


@pytest.mark.asyncio
async def test_multi_agent_stream_line_variants():
    """Branches 215->214 (empty line) and 227->214 (no done) via stream lines."""
    agents = [AgentConfig(id=1, description="d", role="R", goal="g")]

    lines = [
        "",  # empty line -> 215->214 (falsy line, skip)
        "not-json",  # JSONDecodeError -> continue (229-230)
        json.dumps(
            {"message": {"content": ""}, "done": False}
        ),  # empty content 221->227
        json.dumps({"message": {"content": "Hello there friend"}, "done": False}),
        # no done:True -> loop finishes naturally (227->214)
    ]

    factory = _make_client_factory(_make_stream_resp(lines))
    with patch("httpx.AsyncClient", side_effect=factory):
        gen = multi_agent_conversation(agents, "Topic", max_turns=1)
        chunks = [json.loads(c) async for c in gen]

    contents = "".join(c.get("content", "") for c in chunks)
    assert "Hello there friend" in contents
    assert any(c.get("done") for c in chunks)


@pytest.mark.asyncio
async def test_multi_agent_stream_non_200():
    """Branch 214->235: response.status_code != 200 -> skip streaming loop."""
    agents = [AgentConfig(id=1, description="d", role="R", goal="g")]

    factory = _make_client_factory(_make_stream_resp([], status_code=500))
    with patch("httpx.AsyncClient", side_effect=factory):
        gen = multi_agent_conversation(agents, "Topic", max_turns=1)
        chunks = [json.loads(c) async for c in gen]

    # No streamed content -> fallback statement used and turn completes
    assert any(c.get("done") for c in chunks)


@pytest.mark.asyncio
async def test_multi_agent_history_trim():
    """Line 279: history grows beyond 20 -> trimmed to last 10."""
    # Two agents, many turns -> each turn appends 2 history entries. 11 turns -> 22 > 20.
    agents = [
        AgentConfig(id=1, description="d1", role="A", goal="g1"),
        AgentConfig(id=2, description="d2", role="B", goal="g2"),
    ]

    lines = [json.dumps({"message": {"content": "a sentence here"}, "done": True})]

    factory = _make_client_factory(
        None, stream_factory=lambda: _make_stream_resp(list(lines))
    )
    with patch("httpx.AsyncClient", side_effect=factory):
        gen = multi_agent_conversation(agents, "Topic", max_turns=11)
        chunks = [json.loads(c) async for c in gen]

    assert any(c.get("done") for c in chunks)


@pytest.mark.asyncio
async def test_multi_agent_generic_error():
    """Unexpected exception in the worker -> generic system error message."""
    import re as _re

    agents = [AgentConfig(id=1, description="d", role="R", goal="g")]
    factory = _make_client_factory(
        _make_stream_resp([json.dumps({"message": {"content": "hi"}, "done": True})])
    )

    real_sub = _re.sub
    call_state = {"n": 0}

    def fake_sub(*args, **kwargs):
        call_state["n"] += 1
        if call_state["n"] == 1:
            raise ValueError("boom generic")
        return real_sub(*args, **kwargs)

    with (
        patch("httpx.AsyncClient", side_effect=factory),
        patch("app.services.multi_chat.re.sub", side_effect=fake_sub),
    ):
        gen = multi_agent_conversation(agents, "Topic", max_turns=1)
        chunks = [json.loads(c) async for c in gen]

    all_content = "".join(c.get("content", "") for c in chunks)
    # The exception reason is logged, never streamed (py/stack-trace-exposure):
    # pin its ABSENCE, or a leaking "[Error: boom generic]" would satisfy this too.
    assert "boom generic" not in all_content
    assert "the conversation ended unexpectedly" in all_content


@pytest.mark.asyncio
async def test_multi_agent_stream_no_lines():
    """Branch 214->235: status 200 but stream yields zero lines -> loop falls through."""
    agents = [AgentConfig(id=1, description="d", role="R", goal="g")]
    factory = _make_client_factory(_make_stream_resp([], status_code=200))
    with patch("httpx.AsyncClient", side_effect=factory):
        gen = multi_agent_conversation(agents, "Topic", max_turns=1)
        chunks = [json.loads(c) async for c in gen]
    assert any(c.get("done") for c in chunks)


@pytest.mark.asyncio
async def test_multi_agent_preflight_non_200():
    """Line 143: pre-flight Ollama returns non-200 -> logs error, continues."""
    agents = [AgentConfig(id=1, description="d", role="R", goal="g")]
    factory = _make_client_factory(
        _make_stream_resp(
            [json.dumps({"message": {"content": "ok fine here"}, "done": True})]
        ),
        tags_status=503,
    )
    with patch("httpx.AsyncClient", side_effect=factory):
        gen = multi_agent_conversation(agents, "Topic", max_turns=1)
        chunks = [json.loads(c) async for c in gen]
    assert any(c.get("done") for c in chunks)


@pytest.mark.asyncio
async def test_multi_agent_preflight_connection_error():
    """Lines 144-152: pre-flight get raises -> infrastructure error message + return."""
    agents = [AgentConfig(id=1, description="d", role="R", goal="g")]

    class ClientCM:
        async def get(self, *a, **k):
            raise ConnectionError("cannot reach ollama")

        def stream(self, *a, **k):  # pragma: no cover - not reached
            raise AssertionError("stream should not be called")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    with patch("httpx.AsyncClient", side_effect=lambda *a, **k: ClientCM()):
        gen = multi_agent_conversation(agents, "Topic", max_turns=1)
        chunks = [json.loads(c) async for c in gen]

    all_content = "".join(c.get("content", "") for c in chunks)
    assert "Infrastructure Error" in all_content


@pytest.mark.asyncio
async def test_multi_agent_stream_body_exception():
    """Line 231-232: exception while streaming -> full_text set to [Error: ...]."""
    agents = [AgentConfig(id=1, description="d", role="R", goal="g")]

    async def raising_aiter_lines():
        raise RuntimeError("stream broke")
        yield  # pragma: no cover - unreachable, makes this an async generator

    resp = MagicMock()
    resp.status_code = 200
    resp.aiter_lines = raising_aiter_lines
    factory = _make_client_factory(resp)

    with patch("httpx.AsyncClient", side_effect=factory):
        gen = multi_agent_conversation(agents, "Topic", max_turns=1)
        chunks = [json.loads(c) async for c in gen]

    # CodeQL py/stack-trace-exposure: the exception reason is logged, NOT streamed —
    # the client only sees a generic message, and the stream still terminates.
    all_content = "".join(c.get("content", "") for c in chunks)
    assert any(c.get("done") for c in chunks)
    assert "stream broke" not in all_content
    assert "this turn could not be generated" in all_content


@pytest.mark.asyncio
async def test_multi_agent_worker_cancel():
    """Line 334: consumer's finally cancels a worker that is still running.

    We drive the generator in a background task and cancel that task while the
    worker is still alive (blocked in a long stream). Cancellation unwinds the
    generator; the finally block yields the sentinel and then cancels the
    still-pending worker_task (line 334).
    """
    agents = [AgentConfig(id=1, description="d", role="R", goal="g")]

    async def slow_aiter_lines():
        # Emit one chunk, then block for a long time to keep the worker pending.
        yield json.dumps({"message": {"content": "hi there friend"}, "done": False})
        await asyncio.sleep(30)

    resp = MagicMock()
    resp.status_code = 200
    resp.aiter_lines = slow_aiter_lines
    factory = _make_client_factory(resp)

    with patch("httpx.AsyncClient", side_effect=factory):
        gen = multi_agent_conversation(agents, "Topic", max_turns=5)

        collected = []

        async def consume():
            async for chunk in gen:
                collected.append(chunk)

        task = asyncio.create_task(consume())
        # Let the first streamed chunk flow through.
        for _ in range(50):
            await asyncio.sleep(0.01)
            if collected:
                break
        # Cancel the consumer while the worker is still blocked in sleep(30).
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert collected  # at least the first streamed chunk was received


@pytest.mark.asyncio
async def test_multi_chat_max_turns_is_bounded_and_forwarded(client, monkeypatch):
    """#187: max_turns is caller-settable but bounded, and reaches the service.

    An unmocked contract test needs one turn, not twenty sequential local-LLM
    generations — but an unbounded value would let a single request pin the
    model indefinitely, so the schema clamps it to the previous failsafe.

    Uses the shared async `client` fixture rather than TestClient(app): the
    latter runs the app LIFESPAN, which seeds the admin user and therefore needs
    a schema the xdist worker DB does not have — green locally, red under CI's
    `pytest -n auto` (see lessons-learned §17 on full-suite verification).
    """
    from app.api import ai as ai_api
    from app.config import settings

    seen: dict = {}

    def fake_conversation(agents, topic, max_turns=20):
        seen["max_turns"] = max_turns

        async def gen():
            yield '{"agent": 0, "content": "", "done": true}\n'

        return gen()

    monkeypatch.setattr(ai_api, "multi_agent_conversation", fake_conversation)
    url = f"{settings.api_prefix}/ai/multi-chat"
    body = {"topic": "t", "agents": [{"id": 1, "description": "d", "role": "r"}]}

    ok = await client.post(url, json={**body, "max_turns": 1})
    assert ok.status_code == 200
    assert seen["max_turns"] == 1, "max_turns must reach the service"

    # Default is preserved when the caller omits it.
    await client.post(url, json=body)
    assert seen["max_turns"] == 20

    # Out-of-range values are rejected by the schema, not silently clamped.
    for bad in (0, -1, 21, 100):
        rejected = await client.post(url, json={**body, "max_turns": bad})
        assert rejected.status_code == 422, f"max_turns={bad} must be rejected"
