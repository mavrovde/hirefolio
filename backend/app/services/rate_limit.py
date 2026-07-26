"""Small, self-contained in-memory rate limiter.

No third-party dependency: each limiter keeps a per-key sliding window of
request timestamps (monotonic clock) and rejects a request once the window
is full. State lives in the process (a single ``SlidingWindowRateLimiter``
instance), so it is best-effort per backend replica rather than globally
exact — which is fine for the generous limits this backend applies to public
GET endpoints (defense-in-depth against scraping/abuse, not a hard quota).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

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


def _client_ip(request: Request) -> str:
    """Best-effort client IP, honoring a single X-Forwarded-For hop.

    Mirrors the extraction already used for ``GET /stats/public``.
    """
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_dependency(
    limiter: SlidingWindowRateLimiter,
) -> Callable[[Request], Awaitable[None]]:
    """Build a FastAPI dependency that enforces ``limiter`` per client IP."""

    async def _dependency(request: Request) -> None:
        if not limiter.allow(_client_ip(request)):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
            )

    return _dependency
