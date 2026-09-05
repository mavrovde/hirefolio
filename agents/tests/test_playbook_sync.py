"""Drift check for the single-source agent playbook (#115).

The shared working discipline lives in exactly one file — agents/PLAYBOOK.md.
The A2A roster loads it at import time, and every Claude Code charter in
.claude/agents/ must carry the reference block pointing at it. This test fails
when either side stops consuming the single source, which is exactly the drift
the old hand-duplicated setup suffered from.
"""

from pathlib import Path

from agents.common.roster import PROJECT_PLAYBOOK

REPO = Path(__file__).resolve().parents[2]
PLAYBOOK = REPO / "agents" / "PLAYBOOK.md"
CHARTERS = sorted((REPO / ".claude" / "agents").glob("*.md"))


def test_roster_playbook_is_the_committed_file() -> None:
    """roster.PROJECT_PLAYBOOK must BE agents/PLAYBOOK.md, byte for byte."""
    assert PLAYBOOK.is_file(), "agents/PLAYBOOK.md missing — the single source moved?"
    assert PROJECT_PLAYBOOK == PLAYBOOK.read_text(encoding="utf-8")


def test_roster_loads_the_file_rather_than_inlining_it() -> None:
    """Content equality alone cannot detect the duplicate coming BACK: a
    re-inlined, byte-identical PROJECT_PLAYBOOK string would pass the test
    above while resurrecting the drift the single source exists to kill
    (#232 review round 1). So assert on the SOURCE: roster.py must load the
    file and must not carry the playbook text inline."""
    src = (REPO / "agents" / "common" / "roster.py").read_text(encoding="utf-8")
    assert "_PLAYBOOK_PATH" in src and "read_text" in src, (
        "roster.py no longer loads agents/PLAYBOOK.md"
    )
    assert "GROUND EVERYTHING IN REALITY" not in src, (
        "roster.py carries the playbook text inline again — edit "
        "agents/PLAYBOOK.md instead (#115)"
    )


def test_playbook_has_the_load_bearing_sections() -> None:
    """Guard against the file being emptied or replaced by a stub."""
    text = PLAYBOOK.read_text(encoding="utf-8")
    for marker in (
        "GROUND EVERYTHING IN REALITY",
        "NO IRREVERSIBLE LOCAL/INFRA DESTRUCTION",
        "NEVER REAL API KEYS / PAID CREDENTIALS IN TESTS OR CI",
        "MANDATORY REVIEW GATE",
        "PUBLISHED != LIVE",
    ):
        assert marker in text, f"playbook lost its '{marker}' section"


def test_every_charter_references_the_playbook() -> None:
    """Each Claude Code charter must point at the single source (no local fork)."""
    assert CHARTERS, ".claude/agents/ has no charters?"
    for charter in CHARTERS:
        text = charter.read_text(encoding="utf-8")
        assert "agents/PLAYBOOK.md" in text, (
            f"{charter.name} does not reference agents/PLAYBOOK.md — it will "
            "drift from the shared playbook (#115)"
        )
