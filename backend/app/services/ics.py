"""Minimal RFC 5545 (iCalendar) rendering — one VEVENT per call.

Used by the interview calendar (#70 / #247 phase 2) so the owner can drop any
scheduled interview into Apple Calendar / Google Calendar / Outlook without an
integration. #247 phase 3 asks for exactly one ``.ics`` util shared with the
recruiter self-booking flow — this is it, so keep it free of DB/model imports.

The three things naive implementations get wrong, and which are handled here:

* **Escaping** (RFC 5545 §3.3.11) — ``\\``, ``;``, ``,`` and newlines inside a
  TEXT value must be escaped, or a company name like "Acme, Inc." truncates the
  property and the file fails to import.
* **UTC form** (§3.3.5) — timestamps are emitted in the ``…Z`` form, so no
  VTIMEZONE component is needed and no client can guess a local zone wrong.
* **Line folding** (§3.1) — content lines are folded at 75 **octets** (not
  characters) with CRLF + a single space, without splitting a multi-byte UTF-8
  sequence across the fold.
"""

from datetime import UTC, datetime, timedelta

PRODID = "-//Hirefolio//Interview Calendar//EN"

# RFC 5545 §3.1: "Lines of text SHOULD NOT be longer than 75 octets, excluding
# the line break." A continuation line spends one octet on its leading space.
_MAX_OCTETS = 75


def escape_text(value: str) -> str:
    """Escape a TEXT property value per RFC 5545 §3.3.11.

    Backslash first — escaping it after the others would double-escape the
    backslashes those replacements just introduced.
    """
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def format_utc(value: datetime) -> str:
    """Render a datetime as an RFC 5545 UTC timestamp (``20260910T120000Z``).

    A naive datetime is read as UTC — the API layer normalizes on the way in,
    so this only guards values that never carried an offset at all.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def fold_line(line: str) -> str:
    """Fold one content line at 75 octets with CRLF + space continuations."""
    raw = line.encode("utf-8")
    if len(raw) <= _MAX_OCTETS:
        return line

    chunks: list[str] = []
    start = 0
    limit = _MAX_OCTETS
    while start < len(raw):
        end = min(start + limit, len(raw))
        # Never split a multi-byte character. UTF-8 continuation bytes match
        # 0b10xxxxxx, so walking back off them lands on a character boundary in
        # at most three steps — a bounded walk, not a trial-and-error decode.
        while end < len(raw) and raw[end] & 0xC0 == 0x80:
            end -= 1
        chunks.append(raw[start:end].decode("utf-8"))
        start = end
        limit = _MAX_OCTETS - 1  # continuation lines carry a leading space
    return "\r\n ".join(chunks)


def build_event_ics(
    *,
    uid: str,
    summary: str,
    start: datetime,
    duration_minutes: int,
    description: str = "",
    location: str = "",
    cancelled: bool = False,
    dtstamp: datetime | None = None,
) -> str:
    """Render a single-VEVENT VCALENDAR document (CRLF-terminated lines)."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{format_utc(dtstamp or datetime.now(UTC))}",
        f"DTSTART:{format_utc(start)}",
        f"DTEND:{format_utc(start + timedelta(minutes=duration_minutes))}",
        f"SUMMARY:{escape_text(summary)}",
        # A cancelled slot stays exportable on purpose: re-importing it is how a
        # calendar client learns the event is off.
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{escape_text(description)}")
    if location:
        lines.append(f"LOCATION:{escape_text(location)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "".join(f"{fold_line(line)}\r\n" for line in lines)
