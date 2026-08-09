"""Unit tests for app.services.crypto (issue #143).

Covers the Fernet field-level encryption helpers and the EncryptedString
SQLAlchemy type: opt-in behaviour, transparent/backward-compatible reads, and
fail-safe decryption.

NOTE: the Fernet key here is generated locally per-test — it is an encryption
key, NOT a paid-service credential, so CLAUDE.md rule 10 (no real API keys in
tests) is not implicated.
"""

import pytest
from cryptography.fernet import Fernet

from app.services import crypto
from app.services.crypto import (
    _ENC_PREFIX,
    EncryptedString,
    _get_fernet,
    decrypt,
    encrypt,
)


@pytest.fixture
def fernet_key(monkeypatch):
    """Configure a valid Fernet key and return it."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto.settings, "gemini_encryption_key", key)
    return key


@pytest.fixture
def no_key(monkeypatch):
    """Disable encryption (empty key)."""
    monkeypatch.setattr(crypto.settings, "gemini_encryption_key", "")


# --- _get_fernet -----------------------------------------------------------


def test_get_fernet_none_when_unset(no_key):
    assert _get_fernet() is None


def test_get_fernet_builds_when_set(fernet_key):
    assert _get_fernet() is not None


# --- encrypt ---------------------------------------------------------------


def test_encrypt_none_returns_none(fernet_key):
    assert encrypt(None) is None


def test_encrypt_passthrough_when_disabled(no_key):
    assert encrypt("plain-key") == "plain-key"


def test_encrypt_marks_and_hides_value(fernet_key):
    token = encrypt("super-secret")
    assert token is not None
    assert token.startswith(_ENC_PREFIX)
    assert "super-secret" not in token


# --- decrypt ---------------------------------------------------------------


def test_decrypt_none_returns_none(fernet_key):
    assert decrypt(None) is None


def test_decrypt_legacy_plaintext_passthrough(fernet_key):
    # No marker prefix -> value predates encryption; returned as-is.
    assert decrypt("legacy-plaintext") == "legacy-plaintext"


def test_decrypt_marked_but_no_key_returns_none(monkeypatch):
    monkeypatch.setattr(crypto.settings, "gemini_encryption_key", "")
    assert decrypt(f"{_ENC_PREFIX}anything") is None


def test_decrypt_invalid_token_returns_none(fernet_key):
    # Marker present but the token is garbage / from a different key.
    assert decrypt(f"{_ENC_PREFIX}not-a-valid-token") is None


def test_encrypt_decrypt_round_trip(fernet_key):
    assert decrypt(encrypt("round-trip-key")) == "round-trip-key"


def test_decrypt_wrong_key_returns_none(monkeypatch):
    # Encrypt under one key...
    k1 = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto.settings, "gemini_encryption_key", k1)
    token = encrypt("secret")
    # ...then rotate to a different key; decryption must fail safe.
    k2 = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto.settings, "gemini_encryption_key", k2)
    assert decrypt(token) is None


# --- EncryptedString TypeDecorator ----------------------------------------


def test_type_decorator_round_trip(fernet_key):
    col = EncryptedString()
    stored = col.process_bind_param("db-value", dialect=None)
    assert stored is not None and stored.startswith(_ENC_PREFIX)
    assert col.process_result_value(stored, dialect=None) == "db-value"


def test_type_decorator_passthrough_when_disabled(no_key):
    col = EncryptedString()
    stored = col.process_bind_param("db-value", dialect=None)
    assert stored == "db-value"
    assert col.process_result_value(stored, dialect=None) == "db-value"
