"""Hermetic tests for the spec-intake discovery logic (no pipeline run)."""
from agents import intake


def test_slug_from_filename():
    assert intake._slug_from_filename("Add-Uptime Field.md") == "add-uptime-field"


def test_pending_specs_lists_only_real_specs(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "README.md").write_text("x")      # ignored
    (inbox / "TEMPLATE.md").write_text("x")     # ignored
    (inbox / ".gitkeep").write_text("")          # ignored
    (inbox / "notes.txt").write_text("x")        # non-md ignored
    (inbox / "add-ping.md").write_text("spec")   # a real spec
    (inbox / "add-cache.md").write_text("spec")  # a real spec
    monkeypatch.setattr(intake, "INBOX", str(inbox))
    assert set(intake.pending_specs()) == {"add-ping.md", "add-cache.md"}


def test_pending_specs_empty_when_no_inbox(tmp_path, monkeypatch):
    monkeypatch.setattr(intake, "INBOX", str(tmp_path / "nope"))
    assert intake.pending_specs() == []
