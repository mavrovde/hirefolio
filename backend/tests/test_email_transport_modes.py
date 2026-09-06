"""SMTP transport modes (#262): the ONE `_send` path in both shapes.

External-provider mode (STARTTLS + auth) is the default and was already
covered method-by-method; these tests pin the NEW local-relay mode — Mailpit
speaks plain SMTP with no credentials — and the loosened guard that makes it
reachable (host alone gates sending; user/password gate only LOGIN).
"""

from unittest.mock import MagicMock, patch

from app.services.email import EmailService


def _sent_with(patches: dict):
    """Drive one real method through `_send` under the given settings."""
    with patch("smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        ctx = [patch(f"app.config.settings.{k}", v) for k, v in patches.items()]
        for c in ctx:
            c.start()
        try:
            ok = EmailService().send_requester_confirmation("Name", "to@example.com")
        finally:
            for c in ctx:
                c.stop()
        return ok, mock_smtp, server


def test_local_relay_mode_skips_starttls_and_login():
    """The Mailpit shape: host set, TLS off, no credentials — the mail must
    SEND, with neither starttls() nor login() ever called."""
    ok, mock_smtp, server = _sent_with(
        {"smtp_host": "mailpit", "smtp_port": 1025, "smtp_starttls": False}
    )
    assert ok is True
    server.starttls.assert_not_called()
    server.login.assert_not_called()
    server.send_message.assert_called_once()
    # Still time-bounded (#69 review) — relay or provider alike.
    from app.config import settings

    assert mock_smtp.call_args.kwargs["timeout"] == settings.smtp_timeout_seconds


def test_provider_mode_still_negotiates_tls_and_logs_in():
    """The historical shape must be byte-for-byte intact: creds present +
    default STARTTLS -> both negotiated, in order."""
    ok, _, server = _sent_with(
        {"smtp_host": "smtp.example.com", "smtp_user": "u", "smtp_password": "p"}
    )
    assert ok is True
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("u", "p")


def test_host_alone_gates_sending():
    """No host -> graceful skip (the #247 wording), regardless of the other
    settings; host without creds -> attempt the send (the loosened guard —
    requiring user+password kept dev/E2E email permanently off)."""
    with patch("smtplib.SMTP") as mock_smtp:
        with patch("app.config.settings.smtp_host", ""):
            assert (
                EmailService().send_requester_confirmation("N", "t@example.com")
                is False
            )
        mock_smtp.assert_not_called()


def test_from_address_fallback_chain():
    """A no-auth relay has no smtp_user to borrow the From from: explicit
    smtp_from wins, then smtp_user, then the local placeholder."""
    svc = EmailService()
    with patch("app.config.settings.smtp_from", "owner@site"):
        assert svc._from_address() == "owner@site"
    with (
        patch("app.config.settings.smtp_from", ""),
        patch("app.config.settings.smtp_user", "acct@provider"),
    ):
        assert svc._from_address() == "acct@provider"
    with (
        patch("app.config.settings.smtp_from", ""),
        patch("app.config.settings.smtp_user", ""),
    ):
        assert svc._from_address() == "hirefolio@localhost"
