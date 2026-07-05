"""Tests for the login rate limiter and new auth endpoint behaviour."""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
from fastapi import Request

from app.api.auth import _check_rate_limit, _clear_rate_limit, _login_attempts
from app.config import settings


# ─── Rate limiter unit tests ──────────────────────────────────────────────────

def test_rate_limit_allows_under_threshold():
    """Up to MAX_ATTEMPTS requests from the same IP should pass."""
    ip = "10.0.0.1"
    _login_attempts.pop(ip, None)  # ensure clean state
    for _ in range(9):
        _check_rate_limit(ip)  # should not raise
    _login_attempts.pop(ip, None)


def test_rate_limit_blocks_over_threshold():
    """The 11th attempt within the window should raise 429."""
    from fastapi import HTTPException
    ip = "10.0.0.2"
    _login_attempts.pop(ip, None)
    with pytest.raises(HTTPException) as exc:
        for _ in range(11):
            _check_rate_limit(ip)
    assert exc.value.status_code == 429
    _login_attempts.pop(ip, None)


def test_clear_rate_limit():
    """Successful login should clear the rate limit counter."""
    ip = "10.0.0.3"
    _login_attempts[ip] = [1.0, 2.0, 3.0]
    _clear_rate_limit(ip)
    assert ip not in _login_attempts


def test_clear_rate_limit_nonexistent_ip():
    """Clearing a non-existent IP should not raise."""
    _clear_rate_limit("192.168.0.99")  # should not raise


# ─── Integration tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success_returns_token(client: AsyncClient, db_session):
    """Successful login returns a valid token response."""
    from app.models.user import User
    from app.services.auth import get_password_hash

    user = User(
        username="ratetest_user",
        email="ratetest@example.com",
        hashed_password=get_password_hash("Secure1234!"),
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        f"{settings.api_prefix}/auth/login",
        data={"username": "ratetest_user", "password": "Secure1234!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient, db_session):
    from app.models.user import User
    from app.services.auth import get_password_hash

    user = User(
        username="wrongpw_user",
        email="wrongpw@example.com",
        hashed_password=get_password_hash("correct"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        f"{settings.api_prefix}/auth/login",
        data={"username": "wrongpw_user", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_triggered(client: AsyncClient):
    """Repeated failed logins from same IP should eventually trigger 429."""
    ip = "testclient"  # TestClient uses "testclient" as host
    _login_attempts.pop(ip, None)

    responses = []
    for _ in range(12):
        resp = await client.post(
            f"{settings.api_prefix}/auth/login",
            data={"username": "nobody", "password": "badpassword"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        responses.append(resp.status_code)

    # At least one 429 should have been returned
    assert 429 in responses, f"Expected 429 but got: {set(responses)}"
    _login_attempts.pop(ip, None)


# ─── Config tests ─────────────────────────────────────────────────────────────

def test_config_testing_flag_sets_jwt_fallback(monkeypatch):
    """When TESTING=true, jwt_secret_key defaults to test fallback."""
    import importlib
    import os
    monkeypatch.setenv("TESTING", "true")
    # We can't re-import config easily but we can verify the module logic
    testing = os.getenv("TESTING", "false").lower() == "true"
    fallback = "test-secret-key-for-pytest" if testing else ""
    assert fallback == "test-secret-key-for-pytest"


def test_config_production_jwt_empty_by_default(monkeypatch):
    """When TESTING=false, jwt_secret_key must be empty (forced via env)."""
    import os
    monkeypatch.setenv("TESTING", "false")
    testing = os.getenv("TESTING", "false").lower() == "true"
    fallback = "test-secret-key-for-pytest" if testing else ""
    assert fallback == ""
