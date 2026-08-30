"""Issue #177: the JWT signing secret must never be a publicly-known value.

Regression tests for ``app.services.auth.get_jwt_secret_key`` and the startup
guard: an explicit secret is honoured, the committed placeholder and the empty
string are refused (fail-closed), and the local/E2E ephemeral mode issues a
random per-process secret that stays stable within the process.
"""

import pytest

from app.config import INSECURE_JWT_SECRET_KEYS
from app.config import settings as app_settings
from app.services import auth as auth_service
from app.services.auth import (
    InsecureJwtSecretError,
    create_access_token,
    decode_access_token,
    get_jwt_secret_key,
)


@pytest.fixture(autouse=True)
def _reset_ephemeral_secret(monkeypatch):
    """Isolate every test from the cached per-process ephemeral secret."""
    monkeypatch.setattr(auth_service, "_ephemeral_jwt_secret_key", None)
    yield
    monkeypatch.setattr(auth_service, "_ephemeral_jwt_secret_key", None)


def test_explicit_secret_is_returned(monkeypatch):
    monkeypatch.setattr(app_settings, "jwt_secret_key", "an-explicit-strong-secret")
    monkeypatch.setattr(app_settings, "jwt_allow_ephemeral_secret", False)
    assert get_jwt_secret_key() == "an-explicit-strong-secret"


@pytest.mark.parametrize("insecure", sorted(INSECURE_JWT_SECRET_KEYS))
def test_insecure_values_are_refused_without_ephemeral_mode(monkeypatch, insecure):
    """The historical placeholder and the empty string are hard startup errors."""
    monkeypatch.setattr(app_settings, "jwt_secret_key", insecure)
    monkeypatch.setattr(app_settings, "jwt_allow_ephemeral_secret", False)
    with pytest.raises(InsecureJwtSecretError, match="JWT_SECRET_KEY"):
        get_jwt_secret_key()


def test_placeholder_is_in_the_refused_set():
    """The exact committed default of the vulnerable versions stays blocklisted."""
    assert "your-secret-key-change-in-production" in INSECURE_JWT_SECRET_KEYS


def test_ephemeral_mode_issues_random_stable_secret(monkeypatch):
    monkeypatch.setattr(app_settings, "jwt_secret_key", "")
    monkeypatch.setattr(app_settings, "jwt_allow_ephemeral_secret", True)
    first = get_jwt_secret_key()
    second = get_jwt_secret_key()
    assert first == second  # cached: tokens issued by this process verify
    assert first not in INSECURE_JWT_SECRET_KEYS
    assert len(first) == 64  # token_hex(32)


def test_ephemeral_mode_round_trips_tokens(monkeypatch):
    monkeypatch.setattr(app_settings, "jwt_secret_key", "")
    monkeypatch.setattr(app_settings, "jwt_allow_ephemeral_secret", True)
    token = create_access_token({"sub": "admin"})
    payload = decode_access_token(token)
    assert payload is not None and payload["sub"] == "admin"


def test_explicit_secret_wins_over_ephemeral_mode(monkeypatch):
    """An explicitly configured secret is used even when the escape hatch is on."""
    monkeypatch.setattr(app_settings, "jwt_secret_key", "explicit-beats-ephemeral")
    monkeypatch.setattr(app_settings, "jwt_allow_ephemeral_secret", True)
    assert get_jwt_secret_key() == "explicit-beats-ephemeral"
    assert auth_service._ephemeral_jwt_secret_key is None


@pytest.mark.asyncio
async def test_lifespan_refuses_insecure_jwt_secret(monkeypatch):
    """Startup fails fast (not first-login) when no acceptable secret exists."""
    from app.main import app, lifespan

    monkeypatch.setattr(app_settings, "jwt_secret_key", "")
    monkeypatch.setattr(app_settings, "jwt_allow_ephemeral_secret", False)
    with pytest.raises(InsecureJwtSecretError):
        async with lifespan(app):
            pass  # pragma: no cover — lifespan must raise before yielding
