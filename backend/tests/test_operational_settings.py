"""Issue #207: the operational timeouts must be *consumed*, not merely defined.

A settings field that nothing reads is worse than a literal — it advertises a
knob that silently does nothing. So these tests do not assert that the fields
exist; they set each field to a value no literal in the codebase uses, then
assert that the value reaches the HTTP client (or ``asyncio.wait_for``) at the
call site. Reverting any one wiring change turns the corresponding test red.

The sentinel is deliberately absurd (``13.5``) so a passing assertion cannot be
a coincidence of matching the default it replaced.

``httpx.AsyncClient`` is patched with a context manager scoped to the call under
test rather than a fixture, because the suite's own test client is itself an
``httpx.AsyncClient`` — patching it for the whole test would break the harness.
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.config import Settings, settings

SENTINEL = 13.5


class _RecordingClient:
    """Stands in for ``httpx.AsyncClient`` and records every ``timeout`` it sees.

    httpx accepts ``timeout`` either on the client constructor or per request,
    and this codebase uses both spellings, so both are recorded — otherwise a
    test would silently pass on ``None`` for the call sites that hand the
    timeout to ``.get()``/``.stream()`` instead of to the constructor.
    """

    def __init__(self, seen: list[object], get_status: int | None = None):
        self._seen = seen
        # When set, GET succeeds with this status instead of failing, so a
        # caller that pre-flights before doing real work can get past the probe.
        self._get_status = get_status

    def _record(self, kwargs):
        self._seen.append(kwargs.get("timeout"))

    def __call__(self, *args, **kwargs):
        self._record(kwargs)
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        # Requests through the fake fail by default: these tests care only about
        # how the request was CONFIGURED, and every caller handles the error.
        async def _fail(*_args, **kw):
            self._record(kw)
            raise httpx.ConnectError("no network")

        async def _get(*_args, **kw):
            self._record(kw)
            if self._get_status is None:
                raise httpx.ConnectError("no network")
            resp = MagicMock()
            resp.status_code = self._get_status
            return resp

        def _stream(*_args, **kw):
            self._record(kw)
            # ``client.stream(...)`` is an async context manager, so the failure
            # has to surface on __aenter__ rather than on the call itself.
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("no network"))
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        client.post = AsyncMock(side_effect=_fail)
        client.get = AsyncMock(side_effect=_get)
        client.stream = MagicMock(side_effect=_stream)
        return client


def _record_async_client(get_status: int | None = None) -> tuple[list[object], object]:
    seen: list[object] = []
    return seen, patch.object(
        httpx, "AsyncClient", _RecordingClient(seen, get_status=get_status)
    )


async def test_llm_request_timeout_is_used_by_generation(monkeypatch):
    """The 300 s ceiling that used to be duplicated across five call sites."""
    monkeypatch.setattr(settings, "llm_request_timeout_seconds", SENTINEL)
    monkeypatch.setattr(settings, "gemini_api_key", "")  # force the Ollama path
    seen, patcher = _record_async_client()

    from app.services.ai import suggest_tags

    with patcher:
        await suggest_tags("A title", "some post content worth tagging")

    assert SENTINEL in seen, (
        "suggest_tags must build its client from settings.llm_request_timeout_seconds"
    )


async def test_llm_request_timeout_is_used_by_chat(monkeypatch):
    """``chat_with_llm`` is an async *generator*, so it must be iterated."""
    monkeypatch.setattr(settings, "llm_request_timeout_seconds", SENTINEL)
    seen, patcher = _record_async_client()

    from app.services.chat import chat_with_llm

    with patcher:
        async for _ in chat_with_llm([{"role": "user", "content": "hello"}]):
            pass

    assert SENTINEL in seen


async def test_embedding_timeout_is_used(monkeypatch, mocker):
    """Embeddings get their own, much shorter budget than generation.

    ``tests/conftest.py`` autouse-patches ``get_embedding`` so no test reaches
    Ollama. That mock would also hide the wiring under test, so it is lifted
    here — this is the one test that must exercise the real function body, and
    the recording client still guarantees no network call escapes.
    """
    mocker.stopall()
    monkeypatch.setattr(settings, "embedding_request_timeout_seconds", SENTINEL)
    seen, patcher = _record_async_client()

    from app.services.embeddings import get_embedding

    with patcher:
        await get_embedding("text to embed")

    assert SENTINEL in seen


async def test_healthcheck_timeout_is_used_by_the_admin_stats_probe(
    monkeypatch, db_session
):
    """This probe decides the reported AI status, so it must stay tunable."""
    monkeypatch.setattr(settings, "ollama_healthcheck_timeout_seconds", SENTINEL)
    seen, patcher = _record_async_client()

    from app.api.stats import get_stats

    with patcher:
        await get_stats(db=db_session, current_user=MagicMock())

    assert SENTINEL in seen


def test_profile_data_timeout_is_used(monkeypatch):
    """years.py uses the *sync* httpx API, so it is patched separately."""
    monkeypatch.setattr(settings, "profile_data_timeout_seconds", SENTINEL)
    seen: list[object] = []

    def _fake_get(url, **kwargs):
        seen.append(kwargs.get("timeout"))
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "get", _fake_get)

    from app.api.years import _fetch_years_via_http

    _fetch_years_via_http()

    assert SENTINEL in seen


async def test_db_restore_timeout_is_used_and_reported(monkeypatch):
    """The pg_restore ceiling: a big dump legitimately needs longer.

    Also pins the error message, which used to hardcode "300s" and would have
    started lying the moment the ceiling became configurable.
    """
    monkeypatch.setattr(settings, "db_restore_timeout_seconds", 7)
    seen: list[object] = []

    async def _fake_wait_for(awaitable, timeout):
        seen.append(timeout)
        if asyncio.iscoroutine(awaitable):
            awaitable.close()  # we never await it; avoid an unawaited warning
        raise TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", _fake_wait_for)

    upload = MagicMock()
    upload.filename = "dump.sql"
    upload.read = AsyncMock(return_value=b"-- sql")

    from fastapi import HTTPException

    from app.api.admin_sql import restore_database

    proc = MagicMock()
    proc.communicate = MagicMock(return_value=AsyncMock()())
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        with pytest.raises(HTTPException) as excinfo:
            await restore_database(file=upload, current_user=MagicMock())

    assert 7 in seen, (
        "restore must bound itself with settings.db_restore_timeout_seconds"
    )
    assert "after 7s" in excinfo.value.detail, (
        "the timeout message must report the configured ceiling, not a literal"
    )


def test_defaults_match_the_literals_they_replaced():
    """An unchanged .env must produce exactly the previous behaviour."""
    fresh = Settings(_env_file=None)

    assert fresh.llm_request_timeout_seconds == 300.0
    assert fresh.llm_stream_timeout_seconds == 30.0
    assert fresh.embedding_request_timeout_seconds == 30.0
    assert fresh.ollama_healthcheck_timeout_seconds == 2.0
    assert fresh.ollama_startup_check_timeout_seconds == 10.0
    assert fresh.profile_data_timeout_seconds == 5.0
    assert fresh.db_restore_timeout_seconds == 300
    assert fresh.import_max_posts_json_mb == 10
    assert fresh.import_max_posts_per_request == 500


def test_every_new_knob_is_overridable_from_the_environment(monkeypatch):
    """A knob that cannot be set from .env is not a knob."""
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "42.5")
    monkeypatch.setenv("IMPORT_MAX_POSTS_PER_REQUEST", "7")

    fresh = Settings(_env_file=None)

    assert fresh.llm_request_timeout_seconds == 42.5
    assert fresh.import_max_posts_per_request == 7


async def test_startup_check_timeout_is_used(monkeypatch):
    """The startup probe tolerates a still-booting Ollama, so it has its own field."""
    monkeypatch.setattr(settings, "ollama_startup_check_timeout_seconds", SENTINEL)
    monkeypatch.setattr(settings, "jwt_allow_ephemeral_secret", True)
    seen, patcher = _record_async_client()

    from app.main import app, lifespan

    with patcher, contextlib.suppress(Exception):
        async with lifespan(app):
            pass

    assert SENTINEL in seen, (
        "the startup infra check must use settings.ollama_startup_check_timeout_seconds"
    )


async def test_preflight_timeout_is_used_by_the_multi_agent_loop(monkeypatch):
    """The conversation pre-flight keeps its HISTORICAL 5 s budget, not the 2 s
    stats healthcheck: a failed probe aborts the whole conversation, so the two
    must stay separate fields. Reverting the call site to
    ``ollama_healthcheck_timeout_seconds`` makes this assertion fail (#209
    review round 1: the previous test recorded the timeout but asserted only
    the stream sentinel, so the revert kept the suite green)."""
    monkeypatch.setattr(settings, "ollama_preflight_timeout_seconds", SENTINEL)
    # Distinct value on the WRONG field: if the call site reads it, `seen`
    # records this value instead of the sentinel and the test fails.
    monkeypatch.setattr(settings, "ollama_healthcheck_timeout_seconds", SENTINEL + 1)
    seen, patcher = _record_async_client(get_status=200)

    from app.services.multi_chat import AgentConfig, multi_agent_conversation

    agents = [AgentConfig(id=1, description="first agent", name="A")]
    with patcher:
        async for _ in multi_agent_conversation(agents, "a topic", max_turns=1):
            pass

    assert SENTINEL in seen, (
        "the conversation pre-flight must use settings.ollama_preflight_timeout_seconds"
    )
    assert SENTINEL + 1 not in seen, (
        "the pre-flight must NOT read the stats healthcheck budget"
    )


async def test_stream_timeout_is_used_by_the_multi_agent_loop(monkeypatch):
    """The streamed conversation has its own, shorter budget than a full completion.

    Only the *pre-flight* probe and the streaming POST matter here; the loop is
    allowed to fail immediately afterwards, since the assertion is about how the
    request was configured, not about the conversation succeeding.
    """
    monkeypatch.setattr(settings, "llm_stream_timeout_seconds", SENTINEL)
    # The loop pre-flights Ollama with a GET and gives up if it fails, so that
    # probe has to succeed for the streaming POST to be reached at all.
    seen, patcher = _record_async_client(get_status=200)

    from app.services.multi_chat import AgentConfig, multi_agent_conversation

    agents = [
        AgentConfig(id=1, description="first agent", name="A"),
        AgentConfig(id=2, description="second agent", name="B"),
    ]

    with patcher:
        async for _ in multi_agent_conversation(agents, "a topic", max_turns=1):
            pass

    assert SENTINEL in seen, (
        "the streamed POST must use settings.llm_stream_timeout_seconds"
    )
