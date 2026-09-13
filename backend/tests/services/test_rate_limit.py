"""Unit tests for the self-contained in-memory rate limiter."""

import ipaddress
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.config import settings
from app.services.rate_limit import (
    SlidingWindowRateLimiter,
    _is_trusted_proxy,
    _trusted_networks,
    client_ip,
    rate_limit_dependency,
    reset_all_rate_limiters,
)

#: An address inside the shipped `TRUSTED_PROXY_CIDRS` default (172.16.0.0/12) —
#: i.e. what our nginx container looks like to the backend.
PROXY = "172.20.0.9"
#: A real visitor address, as nginx reports it in X-Real-IP.
VISITOR = "203.0.113.9"


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


# --- client-IP derivation (#273) ---------------------------------------------
#
# The key a per-IP control uses must not be settable by the caller. nginx
# APPENDS to X-Forwarded-For ($proxy_add_x_forwarded_for), so hop 0 is whatever
# the client typed; only the tail of the chain, and X-Real-IP, are ours.


def test_default_trusted_cidrs_cover_the_docker_bridge_proxy():
    """The shipped default must actually trust our own nginx container, or the
    containerized topology silently falls back to keying on the proxy's IP —
    one bucket for the whole internet."""
    assert settings.trusted_proxy_cidrs == "172.16.0.0/12"
    assert _is_trusted_proxy(PROXY) is True
    assert _is_trusted_proxy(VISITOR) is False


def test_client_ip_ignores_forwarded_headers_from_an_untrusted_peer():
    """A direct caller (bare dev, an exposed container port) is keyed by its own
    address no matter what it claims in the forwarding headers."""
    request = _make_request(
        client_host="9.9.9.9",
        headers=[
            ("X-Forwarded-For", "1.1.1.1, 2.2.2.2"),
            ("X-Real-IP", "3.3.3.3"),
        ],
    )
    assert client_ip(request) == "9.9.9.9"


def test_client_ip_uses_x_real_ip_from_a_trusted_proxy():
    """Behind our nginx, X-Real-IP ($remote_addr, overwritten on every proxied
    location) is the authoritative client address."""
    request = _make_request(
        client_host=PROXY,
        headers=[
            ("X-Forwarded-For", f"1.1.1.1, {VISITOR}"),
            ("X-Real-IP", VISITOR),
        ],
    )
    assert client_ip(request) == VISITOR


def test_client_ip_spoofed_first_hop_cannot_mint_a_fresh_key():
    """THE BUG (#273): rotating the first X-Forwarded-For hop used to hand the
    attacker a new rate-limit bucket per request. Same real client => same key."""
    keys = {
        client_ip(
            _make_request(
                client_host=PROXY,
                headers=[
                    ("X-Forwarded-For", f"10.0.0.{n}, {VISITOR}"),
                    ("X-Real-IP", VISITOR),
                ],
            )
        )
        for n in range(1, 7)
    }
    assert keys == {VISITOR}


def test_client_ip_distinct_real_clients_behind_the_proxy_get_distinct_keys():
    """The flip side: legitimate visitors must NOT be collapsed into one bucket."""
    first = _make_request(client_host=PROXY, headers=[("X-Real-IP", VISITOR)])
    second = _make_request(client_host=PROXY, headers=[("X-Real-IP", "198.51.100.4")])
    assert client_ip(first) != client_ip(second)


def test_client_ip_falls_back_to_the_last_untrusted_forwarded_hop():
    """No X-Real-IP (a front proxy that only appends XFF): the hop adjacent to
    our infrastructure is the one our proxy observed, never hop 0."""
    request = _make_request(
        client_host=PROXY,
        headers=[("X-Forwarded-For", f"1.1.1.1, {VISITOR}")],
    )
    assert client_ip(request) == VISITOR


def test_client_ip_walks_back_past_our_own_proxy_hops():
    """The edge->nginx chain appends our own addresses; skip them and walk on."""
    request = _make_request(
        client_host=PROXY,
        headers=[("X-Forwarded-For", f"1.1.1.1, {VISITOR}, 172.20.0.3, {PROXY}")],
    )
    assert client_ip(request) == VISITOR


def test_client_ip_ignores_header_values_that_are_not_ip_addresses():
    """Junk cannot become a rate-limit key (it would also grow the key space)."""
    request = _make_request(
        client_host=PROXY,
        headers=[
            ("X-Real-IP", "not-an-ip"),
            ("X-Forwarded-For", "garbage, also-garbage"),
        ],
    )
    assert client_ip(request) == PROXY


def test_client_ip_uses_the_proxy_itself_when_every_hop_is_ours():
    """Server-to-server calls inside the compose network carry no client hop."""
    request = _make_request(
        client_host=PROXY, headers=[("X-Forwarded-For", "172.20.0.3")]
    )
    assert client_ip(request) == PROXY


def test_client_ip_falls_back_to_request_client():
    request = _make_request(client_host="9.9.9.9")
    assert client_ip(request) == "9.9.9.9"


def test_client_ip_unknown_when_no_client_info():
    request = _make_request(client_host=None)
    assert client_ip(request) == "unknown"


def test_trusted_networks_accepts_commas_and_spaces_and_skips_junk():
    assert _trusted_networks("10.0.0.0/8, 192.168.1.7  nonsense/99") == (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("192.168.1.7/32"),
    )


def test_trusted_networks_empty_means_trust_nothing():
    assert _trusted_networks("") == ()


def test_is_trusted_proxy_rejects_non_addresses_and_other_families(monkeypatch):
    """`testclient`/hostnames are not addresses, and an IPv6-only trust list must
    not accidentally match an IPv4 peer."""
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "2001:db8::/32")
    assert _is_trusted_proxy("testclient") is False
    assert _is_trusted_proxy(PROXY) is False
    assert _is_trusted_proxy("2001:db8::5") is True


def test_client_ip_keys_on_the_peer_when_nothing_is_trusted(monkeypatch):
    """Empty TRUSTED_PROXY_CIDRS = trust nothing (documented in .env.example)."""
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "")
    request = _make_request(client_host=PROXY, headers=[("X-Real-IP", VISITOR)])
    assert client_ip(request) == PROXY


def test_served_with_uvicorn_proxy_headers_disabled():
    """`client_ip` treats ``request.client.host`` as the one thing a caller cannot
    forge — so nothing may rewrite it before us. uvicorn's ProxyHeadersMiddleware
    does exactly that (from X-Forwarded-For, hop 0 when FORWARDED_ALLOW_IPS=*),
    which MEASURABLY re-opened this bypass: with it on, 7 requests carrying a
    rotating first hop all passed a 5/60 limiter; with `--no-proxy-headers` the
    6th got 429. The flag is part of the fix, so pin it."""
    dockerfile = (Path(__file__).resolve().parents[2] / "Dockerfile").read_text()
    cmd = next(line for line in dockerfile.splitlines() if line.startswith("CMD "))
    assert "--no-proxy-headers" in cmd


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
