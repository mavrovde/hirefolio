import pytest
from unittest.mock import patch, MagicMock
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
