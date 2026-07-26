"""Unit tests for the self-contained in-memory rate limiter."""

import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.services.rate_limit import (
    SlidingWindowRateLimiter,
    _client_ip,
    rate_limit_dependency,
    reset_all_rate_limiters,
)


def _make_request(client_host: str | None = "1.2.3.4", headers=None) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or [])]
    scope = {
        "type": "http",
        "headers": raw_headers,
        "client": (client_host, 12345) if client_host else None,
    }
    return Request(scope)


def test_allow_within_limit_then_blocks():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False


def test_allow_is_per_key():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("a") is False


def test_allow_evicts_expired_hits(monkeypatch):
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10)
    fake_now = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False
    fake_now[0] += 11  # past the window
    assert limiter.allow("k") is True


def test_reset_clears_hits():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False
    limiter.reset()
    assert limiter.allow("k") is True


def test_reset_all_rate_limiters_resets_every_registered_instance():
    a = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    b = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    assert a.allow("k") is True
    assert b.allow("k") is True
    assert a.allow("k") is False
    assert b.allow("k") is False

    reset_all_rate_limiters()

    assert a.allow("k") is True
    assert b.allow("k") is True


def test_client_ip_prefers_x_forwarded_for():
    request = _make_request(
        client_host="9.9.9.9", headers=[("X-Forwarded-For", "1.1.1.1, 2.2.2.2")]
    )
    assert _client_ip(request) == "1.1.1.1"


def test_client_ip_falls_back_to_request_client():
    request = _make_request(client_host="9.9.9.9")
    assert _client_ip(request) == "9.9.9.9"


def test_client_ip_unknown_when_no_client_info():
    request = _make_request(client_host=None)
    assert _client_ip(request) == "unknown"


@pytest.mark.asyncio
async def test_rate_limit_dependency_allows_then_raises_429():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    dependency = rate_limit_dependency(limiter)
    request = _make_request(client_host="5.5.5.5")

    await dependency(request)  # first call is allowed, returns None

    with pytest.raises(HTTPException) as exc_info:
        await dependency(request)
    assert exc_info.value.status_code == 429
    assert "Too many requests" in exc_info.value.detail
