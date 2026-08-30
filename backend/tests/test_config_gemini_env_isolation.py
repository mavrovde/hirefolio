"""Issue #141: the Gemini env vars must be project-scoped, and provably so.

The control these tests pin is a *security* control, not a convenience: the
generic ``GEMINI_API_KEY`` is a name developers commonly export globally from a
shell profile, and a process environment variable **overrides** ``.env`` in
docker compose — so the generic name silently bound a personal live key into the
local E2E stack, which is exactly the failure #141 exists to prevent.

Every test constructs ``Settings(_env_file=None)`` so a developer's real ``.env``
cannot mask an assertion.
"""

import pytest

from app.config import Settings

LEAKED = "AIza-AMBIENT-KEY-THAT-MUST-NOT-BIND"
PROJECT = "project-scoped-value"


@pytest.fixture(autouse=True)
def _clear_gemini_env(monkeypatch):
    """Start every case from a known-empty environment."""
    for name in (
        "GEMINI_API_KEY",
        "HIREFOLIO_GEMINI_API_KEY",
        "GEMINI_ENCRYPTION_KEY",
        "HIREFOLIO_GEMINI_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_ambient_gemini_api_key_cannot_bind(monkeypatch):
    """The generic name must be ignored — this is the whole point of #141."""
    monkeypatch.setenv("GEMINI_API_KEY", LEAKED)

    assert Settings(_env_file=None).gemini_api_key == "", (
        "an ambient GEMINI_API_KEY must NOT reach the application"
    )


def test_project_scoped_gemini_api_key_binds(monkeypatch):
    """...while the project-scoped name still configures the feature."""
    monkeypatch.setenv("HIREFOLIO_GEMINI_API_KEY", PROJECT)

    assert Settings(_env_file=None).gemini_api_key == PROJECT


def test_project_name_wins_when_both_are_set(monkeypatch):
    """A developer with both set gets the project's value, never the ambient one."""
    monkeypatch.setenv("GEMINI_API_KEY", LEAKED)
    monkeypatch.setenv("HIREFOLIO_GEMINI_API_KEY", PROJECT)

    assert Settings(_env_file=None).gemini_api_key == PROJECT


def test_ambient_encryption_key_cannot_bind(monkeypatch):
    """The at-rest encryption key is namespaced for the same reason (#143)."""
    monkeypatch.setenv("GEMINI_ENCRYPTION_KEY", "ambient-fernet-key")

    assert Settings(_env_file=None).gemini_encryption_key == ""


def test_project_scoped_encryption_key_binds(monkeypatch):
    monkeypatch.setenv("HIREFOLIO_GEMINI_ENCRYPTION_KEY", "project-fernet-key")

    assert Settings(_env_file=None).gemini_encryption_key == "project-fernet-key"


def test_ambient_model_override_cannot_force_a_premium_tier(monkeypatch):
    """Model selection is a COST control, so it is namespaced too.

    An ambient ``GEMINI_MODEL`` pointing at a premium tier would silently raise
    the per-call price of every suggestion — the same class of unbounded,
    invisible spend #141 was filed about.
    """
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("HIREFOLIO_GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro-expensive")

    settings = Settings(_env_file=None)

    assert settings.gemini_model != "gemini-3.1-pro-expensive"

    monkeypatch.setenv("HIREFOLIO_GEMINI_MODEL", "gemini-flash-cheap")
    assert Settings(_env_file=None).gemini_model == "gemini-flash-cheap"


def test_direct_construction_uses_the_alias_not_the_field_name():
    """Construct by ALIAS; ``populate_by_name`` must stay off.

    Enabling ``populate_by_name`` to make ``Settings(gemini_api_key=...)`` work
    also re-admits the field name as an *environment* source — which lets the
    generic ``GEMINI_API_KEY`` bind again and silently undoes this whole issue.
    That regression was caught by the tests above, so the trade-off is recorded
    here: the alias is the supported way in, and the field name is inert.
    """
    assert (
        Settings(_env_file=None, HIREFOLIO_GEMINI_API_KEY="direct").gemini_api_key
        == "direct"
    )
