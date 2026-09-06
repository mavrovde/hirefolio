"""RFC 5545 rendering unit tests (#70 / #247 phase 2).

The three failure modes that make an .ics silently un-importable are escaping,
non-UTC timestamps and unfolded long lines — one test each, plus the multi-byte
fold boundary that a naive character-based folder corrupts.
"""

from datetime import UTC, datetime, timedelta, timezone

from app.services.ics import build_event_ics, escape_text, fold_line, format_utc


def _unfold(document: str) -> str:
    """Reverse RFC 5545 line folding, the way a calendar client does."""
    return document.replace("\r\n ", "")


def test_escape_text_escapes_every_special_character():
    # Backslash must be escaped FIRST or the escapes below get double-escaped.
    assert escape_text("a\\b;c,d") == "a\\\\b\\;c\\,d"
    assert (
        escape_text("line1\r\nline2\nline3\rline4") == "line1\\nline2\\nline3\\nline4"
    )


def test_format_utc_converts_offsets_and_assumes_utc_for_naive():
    aware = datetime(2026, 9, 10, 16, 30, tzinfo=timezone(timedelta(hours=2)))
    assert format_utc(aware) == "20260910T143000Z"
    # Built via fromisoformat so the value is genuinely naive (ruff DTZ001
    # forbids a bare datetime(...) literal, which is exactly the input here).
    naive = datetime.fromisoformat("2026-09-10T14:30:00")
    assert naive.tzinfo is None
    assert format_utc(naive) == "20260910T143000Z"


def test_fold_line_leaves_short_lines_alone():
    assert fold_line("SUMMARY:short") == "SUMMARY:short"


def test_fold_line_folds_long_lines_at_75_octets_and_unfolds_back():
    line = "DESCRIPTION:" + "x" * 400
    folded = fold_line(line)
    segments = folded.split("\r\n ")
    assert len(segments) > 1
    assert len(segments[0].encode()) == 75
    assert all(len(s.encode()) <= 74 for s in segments[1:])
    assert folded.replace("\r\n ", "") == line


def test_fold_line_never_splits_a_multibyte_character():
    line = "SUMMARY:" + "ä" * 80  # 2 octets each -> the boundary lands mid-character
    folded = fold_line(line)
    assert folded.replace("\r\n ", "") == line
    # A character-based folder would emit 150-octet segments here.
    for segment in folded.split("\r\n "):
        assert len(segment.encode()) <= 75


def test_build_event_ics_renders_a_minimal_valid_vevent():
    document = build_event_ics(
        uid="abc@example.test",
        summary="Interview: Acme, Inc. — Staff Engineer",
        start=datetime(2026, 9, 10, 12, 0, tzinfo=UTC),
        duration_minutes=45,
        description="Video interview.\nInterviewer: Rita",
        location="https://meet.example/x",
        dtstamp=datetime(2026, 9, 6, 8, 0, tzinfo=UTC),
    )
    assert document.startswith("BEGIN:VCALENDAR\r\n")
    assert document.endswith("END:VCALENDAR\r\n")
    lines = _unfold(document).split("\r\n")
    assert "VERSION:2.0" in lines
    assert "UID:abc@example.test" in lines
    assert "DTSTAMP:20260906T080000Z" in lines
    assert "DTSTART:20260910T120000Z" in lines
    assert "DTEND:20260910T124500Z" in lines  # start + duration_minutes
    assert "STATUS:CONFIRMED" in lines
    # The comma in the company name must be escaped, or the property truncates.
    assert "SUMMARY:Interview: Acme\\, Inc. — Staff Engineer" in lines
    assert "DESCRIPTION:Video interview.\\nInterviewer: Rita" in lines
    assert "LOCATION:https://meet.example/x" in lines


def test_build_event_ics_omits_empty_optionals_and_marks_cancellations():
    document = build_event_ics(
        uid="u@h",
        summary="s",
        start=datetime(2026, 9, 10, 12, 0, tzinfo=UTC),
        duration_minutes=30,
        cancelled=True,
    )
    assert "STATUS:CANCELLED" in document
    assert "DESCRIPTION" not in document
    assert "LOCATION" not in document


def test_build_event_ics_defaults_dtstamp_to_now():
    document = build_event_ics(
        uid="u@h",
        summary="s",
        start=datetime(2026, 9, 10, 12, 0, tzinfo=UTC),
        duration_minutes=30,
    )
    stamp = next(line for line in document.split("\r\n") if line.startswith("DTSTAMP:"))
    parsed = datetime.strptime(stamp[len("DTSTAMP:") :], "%Y%m%dT%H%M%SZ").replace(
        tzinfo=UTC
    )
    assert abs((datetime.now(UTC) - parsed).total_seconds()) < 60
