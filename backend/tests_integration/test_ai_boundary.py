"""The AI boundary, exercised for real: backend → WireMock over the network.

The happy path proves the wiring; the `faults` cases prove the delay/error
mappings actually traverse the boundary — the foundation for asserting the
#207 timeout/fallback budgets at this tier.
"""

import time

import httpx
import pytest

from conftest import API


def _chat(
    client: httpx.Client, content: str, timeout: float = 25.0
) -> tuple[str, float]:
    start = time.monotonic()
    with client.stream(
        "POST",
        f"{API}/ai/chat",
        json={"messages": [{"role": "user", "content": content}]},
        timeout=timeout,
    ) as resp:
        assert resp.status_code == 200
        body = b"".join(resp.iter_bytes()).decode(errors="replace")
    return body, time.monotonic() - start


def test_chat_streams_the_stubbed_reply(client: httpx.Client):
    body, elapsed = _chat(client, "hello integration tier")
    assert "[wiremock] deterministic chat reply." in body
    # A stubbed reply should be near-instant; the budget exists to catch a
    # request escaping WireMock to a real model server (minutes, or a hang).
    # 15 s absorbs shared-runner cold-start/SSE-handshake noise because this
    # case GATES publishing (#261 review major 5) — the tight timing
    # diagnostics live in the non-gating `faults` cases.
    assert elapsed < 15.0


@pytest.mark.faults
def test_injected_delay_traverses_the_boundary(client: httpx.Client):
    """The 8 s WireMock delay must be observable end-to-end — proof that
    fault injection reaches the real code path, not a bypass."""
    body, elapsed = _chat(client, "please be __wiremock_slow__ today")
    assert elapsed >= 7.5
    assert "slow reply" in body


@pytest.mark.faults
def test_injected_upstream_error_terminates_cleanly(client: httpx.Client):
    """An upstream 500 must not hang the stream: the request terminates
    within a tight budget and the connection closes."""
    start = time.monotonic()
    with client.stream(
        "POST",
        f"{API}/ai/chat",
        json={"messages": [{"role": "user", "content": "__wiremock_error__"}]},
        timeout=15.0,
    ) as resp:
        # Behavior contract: the endpoint answers (SSE begins with 200) and
        # ENDS — no hang, no indefinite retry against the dead upstream.
        assert resp.status_code == 200
        resp.read()
    assert time.monotonic() - start < 10.0
