"""encrypt gemini_api_key at rest

Widens ``users.gemini_api_key`` from ``VARCHAR(255)`` to ``TEXT`` (a Fernet
token plus the ``enc:v1:`` marker is longer than the raw ~40-char key) and
encrypts any existing plaintext value in place.

Safety / issue #143:

* The data step is **guarded by the encryption key**: when
  ``GEMINI_ENCRYPTION_KEY`` is unset, ``app.services.crypto.encrypt`` returns the
  value unchanged, so nothing is rewritten — the column merely widens (harmless,
  reversible) and rows stay plaintext, still readable via the passthrough. When
  the key IS set, existing plaintext rows are encrypted with the ``enc:v1:``
  marker.
* It is **idempotent**: values already carrying the marker are skipped, so
  re-running never double-encrypts.
* Blast radius is tiny (only rows with a key set — in practice the single admin).

Revision ID: encrypt0002
Revises: baseline0001
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# NOTE: ``app.*`` is imported lazily inside upgrade()/downgrade() (not at module
# top-level) so alembic commands that only build the revision map — e.g.
# ``alembic heads``/``history`` — don't require the backend package on sys.path
# (env.py adds it only when actually running migrations).

# revision identifiers, used by Alembic.
revision: str = "encrypt0002"
down_revision: str | None = "baseline0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.services.crypto import _ENC_PREFIX, encrypt

    op.alter_column(
        "users",
        "gemini_api_key",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, gemini_api_key FROM users WHERE gemini_api_key IS NOT NULL")
    ).fetchall()
    for row in rows:
        raw = row.gemini_api_key
        if raw.startswith(_ENC_PREFIX):
            continue  # already encrypted — idempotent
        enc = encrypt(raw)
        if enc == raw:
            continue  # encryption disabled (no key) — leave plaintext as-is
        conn.execute(
            sa.text("UPDATE users SET gemini_api_key = :v WHERE id = :id"),
            {"v": enc, "id": row.id},
        )


def downgrade() -> None:
    from app.services.crypto import _ENC_PREFIX, decrypt

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, gemini_api_key FROM users WHERE gemini_api_key IS NOT NULL")
    ).fetchall()
    for row in rows:
        raw = row.gemini_api_key
        if not raw.startswith(_ENC_PREFIX):
            continue
        plain = decrypt(raw)
        conn.execute(
            sa.text("UPDATE users SET gemini_api_key = :v WHERE id = :id"),
            {"v": plain, "id": row.id},
        )

    op.alter_column(
        "users",
        "gemini_api_key",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
