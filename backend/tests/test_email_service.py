from unittest.mock import MagicMock, patch

import pytest

from app.services.email import EmailService


@pytest.fixture
def email_service():
    return EmailService()


def test_send_email_success(email_service):
    # Test proper sending via public method
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        with (
            patch("app.config.settings.smtp_host", "localhost"),
            patch("app.config.settings.smtp_user", "user"),
            patch("app.config.settings.smtp_password", "pass"),
        ):
            res = email_service.send_requester_confirmation("Name", "test@test.com")
            assert res is True
            mock_server.send_message.assert_called_once()


def test_send_email_failure(email_service):
    with patch("smtplib.SMTP", side_effect=Exception("SMTP Error")):
        with (
            patch("app.config.settings.smtp_host", "localhost"),
            patch("app.config.settings.smtp_user", "user"),
            patch("app.config.settings.smtp_password", "pass"),
        ):
            res = email_service.send_requester_confirmation("Name", "test@test.com")
            assert res is False


def test_send_cv_notification_details(email_service):
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        with (
            patch("app.config.settings.smtp_host", "localhost"),
            patch("app.config.settings.smtp_user", "user"),
            patch("app.config.settings.smtp_password", "pass"),
        ):
            email_service.send_cv_request_notification(
                "Name", "email@test.com", "Company", "Msg", "Pos", True
            )
            mock_server.send_message.assert_called_once()
            call_args = mock_server.send_message.call_args[0][0]
            assert "CV Request" in call_args["Subject"]
            assert "Name" in call_args.get_content()


def test_email_config_missing(email_service):
    # Test early return when config is missing
    with patch("app.config.settings.smtp_host", None):
        assert (
            email_service.send_requester_confirmation("Name", "test@test.com") is False
        )


def test_requester_confirmation_uses_owner_name(email_service):
    """The confirmation copy derives from OWNER_NAME (#65) — pinned with a
    DISTINCT value so a hardcoded-name revert fails (#255 review mutation
    finding: with the default settings the old literal passed unchanged)."""
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        with (
            patch("app.config.settings.smtp_host", "localhost"),
            patch("app.config.settings.smtp_user", "user"),
            patch("app.config.settings.smtp_password", "pass"),
            patch("app.config.settings.owner_name", "Pin Q. Owner"),
        ):
            assert (
                email_service.send_requester_confirmation("Rita", "r@x.example") is True
            )
            msg = mock_server.send_message.call_args[0][0]
            assert "Pin Q. Owner" in msg["Subject"]
            assert "Pin Q. Owner's CV" in msg.get_content()
