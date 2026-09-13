"""Small, self-contained in-memory rate limiter.

No third-party dependency: each limiter keeps a per-key sliding window of
request timestamps (monotonic clock) and rejects a request once the window
is full. State lives in the process (a single ``SlidingWindowRateLimiter``
instance), so it is best-effort per backend replica rather than globally
exact — which is fine for the generous limits this backend applies to public
GET endpoints (defense-in-depth against scraping/abuse, not a hard quota).
"""

from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from functools import lru_cache

from fastapi import HTTPException, Request, status

from app.config import settings

# Every limiter created registers itself here so tests can reset all
# module-level rate-limit state in one call, regardless of which API module
# instantiated it (see `reset_all_rate_limiters`).
_registered_limiters: list[SlidingWindowRateLimiter] = []


class SlidingWindowRateLimiter:
    """Per-key sliding-window rate limiter (in-memory, single-process)."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        _registered_limiters.append(self)

    def allow(self, key: str) -> bool:
        """Record a hit for ``key``; return whether it is within the limit."""
        now = time.monotonic()
        window_start = now - self.window_seconds
        hits = self._hits[key]
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        """Clear all recorded hits.

        Used to isolate tests from module-level rate-limit state so request
        counts from one test never bleed into the next.
        """
        self._hits.clear()


def reset_all_rate_limiters() -> None:
    """Reset every registered limiter. Intended for test setup/teardown."""
    for limiter in _registered_limiters:
        limiter.reset()


Networks = tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]


@lru_cache(maxsize=8)
def _trusted_networks(raw: str) -> Networks:
    """Parse ``TRUSTED_PROXY_CIDRS`` (space/comma separated) into networks.

    Cached on the raw string: this runs on every rate-limited request, and the
    setting changes only when the process restarts (or a test overrides it).
    Invalid entries are skipped rather than fatal — the same forgiving parse
    ``proxy/generate-admin-config.sh`` applies to the identically-named knob,
    so one typo cannot take the backend down.
    """
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in raw.replace(",", " ").split():
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _is_trusted_proxy(host: str) -> bool:
    """Whether ``host`` is one of our reverse proxies (so its headers count)."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # Not an IP at all (a hostname, "testclient", junk) — never trusted.
        return False
    return any(
        address in network
        for network in _trusted_networks(settings.trusted_proxy_cidrs)
    )


def _valid_ip(value: str) -> str | None:
    """Return ``value`` when it is a bare IP address, else ``None``."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return None
    return value


def client_ip(request: Request) -> str:
    """The client address a per-IP control may safely key on.

    SECURITY (#273): the previous implementation returned the FIRST
    ``X-Forwarded-For`` hop, which is whatever the caller typed — nginx
    APPENDS with ``$proxy_add_x_forwarded_for``, it never replaces — so an
    attacker rotated that header and got a fresh rate-limit bucket per request.

    Forwarding headers are believed only when the PEER is a trusted proxy
    (``TRUSTED_PROXY_CIDRS``, same meaning as the proxy container's knob), and
    then in this order:

    1. ``X-Real-IP`` — our nginx sets it to ``$remote_addr`` on every proxied
       location (``proxy/default.conf.template``), overwriting anything the
       client sent, and with ``real_ip_recursive`` that address is already the
       real client behind the shared-host Caddy edge.
    2. the LAST ``X-Forwarded-For`` hop that is not itself a trusted proxy —
       the hop adjacent to our own infrastructure, i.e. the one our proxy
       observed rather than one the client appended.
    3. the peer address itself (server-to-server calls carry no forwarded
       headers at all).

    An untrusted peer — bare-metal dev, a direct hit on the container port —
    is keyed by its own address, so spoofed headers buy nothing there either.
    """
    peer = request.client.host if request.client else None
    if peer is None:
        return "unknown"
    if not _is_trusted_proxy(peer):
        return peer
    real_ip = _valid_ip(request.headers.get("x-real-ip", "").strip())
    if real_ip:
        return real_ip
    forwarded = request.headers.get("x-forwarded-for", "")
    for hop in reversed(forwarded.split(",")):
        candidate = _valid_ip(hop.strip())
        if candidate and not _is_trusted_proxy(candidate):
            return candidate
    return peer


def rate_limit_dependency(
    limiter: SlidingWindowRateLimiter,
) -> Callable[[Request], Awaitable[None]]:
    """Build a FastAPI dependency that enforces ``limiter`` per client IP."""

    async def _dependency(request: Request) -> None:
        if not limiter.allow(client_ip(request)):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
            )

    return _dependency
