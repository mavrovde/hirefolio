"""Interview reminder emails (#247 criterion 3, reminder clause).

Two layers on purpose: the SERVICE tests pin the message itself (recipient,
subject, the .ics attachment, the graceful skip), and the API tests pin WHEN a
reminder fires — schedule yes, real reschedule yes, outcome-only PATCH no,
same-instant "reschedule" no — with the service faked at the boundary
(rule 10: no test may open a real SMTP connection).
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.email import EmailService

OPPS = f"{settings.api_prefix}/admin/opportunities"
IVS = f"{settings.api_prefix}/admin/interviews"

KW = {
    "company": "Acme GmbH",
    "role_title": "Staff Engineer",
    "kind": "video",
    "scheduled_at_iso": "2026-09-10T09:00:00+00:00",
    "duration_minutes": 60,
    "location_or_link": "https://meet.example/1",
    "interviewer": "Ada",
    "ics_payload": "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n",
}


# --------------------------------------------------------------- service ----


def test_reminder_skips_gracefully_when_smtp_unconfigured():
    """The criterion's own words: 'skipped gracefully when SMTP is
    unconfigured'. No exception, no connection attempt, False back."""
    with patch("smtplib.SMTP") as mock_smtp:
        with patch("app.config.settings.smtp_host", ""):
            assert EmailService().send_interview_reminder(**KW) is False
        mock_smtp.assert_not_called()


def test_reminder_sends_with_ics_attachment():
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        with (
            patch("app.config.settings.smtp_host", "localhost"),
            patch("app.config.settings.smtp_user", "user"),
            patch("app.config.settings.smtp_password", "pass"),
        ):
            assert EmailService().send_interview_reminder(**KW) is True

        mock_server.send_message.assert_called_once()
        msg = mock_server.send_message.call_args.args[0]
        assert msg["To"] == settings.admin_email
        assert "Interview scheduled: Staff Engineer at Acme GmbH" in msg["Subject"]
        # The invite must travel WITH the mail — the calendar app it lands in
        # is what carries the actual timed alarm.
        attachments = [part for part in msg.iter_attachments()]
        assert len(attachments) == 1
        assert attachments[0].get_filename() == "interview.ics"
        assert attachments[0].get_content_type() == "text/calendar"
        assert b"BEGIN:VCALENDAR" in attachments[0].get_payload(decode=True)
        # Time-bounded connection, like every sibling (#69 review).
        assert mock_smtp.call_args.kwargs["timeout"] == settings.smtp_timeout_seconds


def test_reminder_reschedule_wording_and_failure_path():
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        with (
            patch("app.config.settings.smtp_host", "localhost"),
            patch("app.config.settings.smtp_user", "user"),
            patch("app.config.settings.smtp_password", "pass"),
        ):
            assert (
                EmailService().send_interview_reminder(**KW, rescheduled=True) is True
            )
            msg = mock_server.send_message.call_args.args[0]
            assert msg["Subject"].startswith("Interview rescheduled:")

    with patch("smtplib.SMTP", side_effect=Exception("SMTP Error")):
        with (
            patch("app.config.settings.smtp_host", "localhost"),
            patch("app.config.settings.smtp_user", "user"),
            patch("app.config.settings.smtp_password", "pass"),
        ):
            # A broken relay is a logged False, never an exception.
            assert EmailService().send_interview_reminder(**KW) is False


# ------------------------------------------------------------------- API ----


async def _opportunity(client: AsyncClient) -> dict:
    r = await client.post(
        OPPS, json={"company": "Acme GmbH", "role_title": "Staff Engineer"}
    )
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def sent(monkeypatch):
    """Capture reminder calls at the SERVICE boundary — the API tests care
    about WHEN it fires and with WHAT, not about SMTP mechanics."""
    calls: list[dict] = []

    def fake(self, **kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(EmailService, "send_interview_reminder", fake)
    return calls


@pytest.mark.asyncio
async def test_scheduling_fires_one_reminder_with_the_event(client, sent):
    opp = await _opportunity(client)
    r = await client.post(
        f"{OPPS}/{opp['id']}/interviews",
        json={"scheduled_at": "2026-09-10T09:00:00+00:00", "interviewer": "Ada"},
    )
    assert r.status_code == 201

    assert len(sent) == 1
    call = sent[0]
    assert call["company"] == "Acme GmbH"
    assert call["role_title"] == "Staff Engineer"
    assert call["rescheduled"] is False
    assert call["scheduled_at_iso"] == "2026-09-10T09:00:00+00:00"
    # The attachment is the SAME event the export route serves (shared
    # builder): stable UID and a real VEVENT.
    assert "BEGIN:VEVENT" in call["ics_payload"]
    assert f"UID:{r.json()['id']}@" in call["ics_payload"]


@pytest.mark.asyncio
async def test_reschedule_fires_but_outcome_and_noop_do_not(client, sent):
    opp = await _opportunity(client)
    r = await client.post(
        f"{OPPS}/{opp['id']}/interviews",
        json={"scheduled_at": "2026-09-10T09:00:00+00:00"},
    )
    iv = r.json()
    assert len(sent) == 1  # the scheduling one

    # Outcome-only PATCH: not calendar news, no mail.
    assert (
        await client.patch(f"{IVS}/{iv['id']}", json={"outcome": "passed"})
    ).status_code == 200
    assert len(sent) == 1

    # Same-instant "reschedule": a no-op move, no mail.
    assert (
        await client.patch(
            f"{IVS}/{iv['id']}", json={"scheduled_at": "2026-09-10T09:00:00+00:00"}
        )
    ).status_code == 200
    assert len(sent) == 1

    # A real move: exactly one more, flagged as a reschedule, new instant.
    assert (
        await client.patch(
            f"{IVS}/{iv['id']}", json={"scheduled_at": "2026-09-11T10:00:00+00:00"}
        )
    ).status_code == 200
    assert len(sent) == 2
    assert sent[1]["rescheduled"] is True
    assert sent[1]["scheduled_at_iso"] == "2026-09-11T10:00:00+00:00"


@pytest.mark.asyncio
async def test_scheduling_succeeds_even_if_the_reminder_blows_up(client, monkeypatch):
    """The _notify idiom: a mail failure must never fail the scheduling."""

    def boom(self, **kwargs):
        raise RuntimeError("relay on fire")

    monkeypatch.setattr(EmailService, "send_interview_reminder", boom)
    opp = await _opportunity(client)
    r = await client.post(
        f"{OPPS}/{opp['id']}/interviews",
        json={"scheduled_at": "2026-09-10T09:00:00+00:00"},
    )
    assert r.status_code == 201
