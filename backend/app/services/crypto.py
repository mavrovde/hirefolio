"""Transparent field-level encryption for sensitive at-rest secrets.

Encrypts the per-user Gemini API key (a paid, billable credential) using Fernet
(AES-128-CBC + HMAC-SHA256). The Fernet key comes from
``settings.gemini_encryption_key`` (env ``GEMINI_ENCRYPTION_KEY``).

Design goals (issue #143):

* **Opt-in / backward compatible.** When ``gemini_encryption_key`` is empty,
  encryption is disabled and values pass through as plaintext, so local/dev/E2E
  setups that never configure a key keep working. Production sets the env var to
  encrypt the credential at rest.
* **Transparent, non-breaking reads.** Legacy plaintext values (written before
  encryption was enabled — i.e. without the ``enc:v1:`` marker) are returned
  as-is, so turning encryption on never breaks or loses existing rows. New
  writes are stored encrypted with the marker prefix.
* **Fail safe, never fail loud on read.** If a marked value cannot be decrypted
  (key missing or rotated), we log a warning and return ``None`` (treated as "no
  key"), which degrades gracefully to the env-level fallback rather than
  crashing ``/auth/me`` or the AI endpoints.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

# Marker prefix stamped onto ciphertext so reads can unambiguously tell an
# encrypted value from a legacy plaintext one (and stay idempotent across
# re-encryption / migration runs).
_ENC_PREFIX = "enc:v1:"


def _get_fernet() -> Fernet | None:
    """Build a Fernet from the configured key, or ``None`` when unset.

    A malformed key raises (``ValueError`` from ``Fernet``) on purpose: a broken
    ``GEMINI_ENCRYPTION_KEY`` is a deploy-time misconfiguration worth surfacing.
    """
    key = settings.gemini_encryption_key
    if not key:
        return None
    return Fernet(key.encode())


def encrypt(value: str | None) -> str | None:
    """Encrypt ``value`` for storage; passthrough when encryption is disabled."""
    if value is None:
        return None
    fernet = _get_fernet()
    if fernet is None:
        return value
    token = fernet.encrypt(value.encode()).decode()
    return f"{_ENC_PREFIX}{token}"


def decrypt(value: str | None) -> str | None:
    """Decrypt a stored value; passthrough legacy plaintext, fail safe on error."""
    if value is None:
        return None
    if not value.startswith(_ENC_PREFIX):
        # Legacy plaintext (or written while encryption was disabled).
        return value
    token = value[len(_ENC_PREFIX) :]
    fernet = _get_fernet()
    if fernet is None:
        logger.warning(
            "Encrypted secret found but GEMINI_ENCRYPTION_KEY is not set; "
            "cannot decrypt — treating as unset."
        )
        return None
    try:
        return fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        logger.warning(
            "Failed to decrypt secret (invalid token or rotated key) — "
            "treating as unset."
        )
        return None


class EncryptedString(TypeDecorator[str]):
    """SQLAlchemy column type that encrypts on write and decrypts on read.

    Backed by ``Text`` because a Fernet token (plus marker prefix) is longer than
    the original 40-char key and can exceed a ``String(255)`` column.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        return encrypt(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        return decrypt(value)
