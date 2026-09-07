"""Black-box integration tier (#260).

These tests hit a RUNNING stack over real HTTP — no ASGI transport, no
monkeypatching. Bring it up with `./run_integration_tests.sh` (which boots
docker-compose.yml + docker-compose.inttest.yml, where the `ollama` service is
WireMock). This directory is deliberately OUTSIDE `backend/tests/` so the unit
run (`pytest` with testpaths=["tests"]) never collects it, and vice versa.

Environment:
  BACKEND_URL  direct backend origin        (default http://localhost:8000)
  PUBLIC_URL   through the reverse proxy    (default http://localhost:4200)
  E2E creds    seeded by scripts/seed_e2e_user.py (admin / admin123)
"""

import os

import httpx
import pytest

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:4200").rstrip("/")
API = f"{BACKEND_URL}/api/app"


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client: httpx.Client) -> str:
    # OAuth2PasswordRequestForm: FORM-encoded, not JSON.
    resp = client.post(
        f"{API}/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, (
        f"admin login failed ({resp.status_code}): run scripts/seed_e2e_user.py "
        "inside the backend container first (run_integration_tests.sh does)."
    )
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


def post_contact(client: httpx.Client, payload: dict) -> httpx.Response:
    """POST the public contact form, absorbing the 5/60s rate limit.

    RATE-LIMIT BUDGET (#296 round 2, re-hit by #298 round 2): the tier posts
    FIVE contacts per full run — exactly the budget — so a back-to-back local
    re-run starts inside a saturated window. Every contact-posting test MUST
    go through this helper: the sliding window frees a slot 60s after the hit
    that took it, so a partial wait cannot clear it.
    """
    import time

    resp = client.post(f"{API}/interactions/contact", json=payload)
    for _ in range(3):
        if resp.status_code != 429:
            break
        time.sleep(61)
        resp = client.post(f"{API}/interactions/contact", json=payload)
    return resp
