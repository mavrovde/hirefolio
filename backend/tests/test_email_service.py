import unittest
from unittest.mock import patch, MagicMock
from app.services.email import EmailService


class TestEmailService(unittest.TestCase):
    @patch("app.services.email.settings")
    @patch("smtplib.SMTP")
    def test_send_cv_request_notification_success(self, mock_smtp, mock_settings):
        # Setup mock settings
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_user = "user@example.com"
        mock_settings.smtp_password = "password"
        mock_settings.admin_email = "admin@example.com"

        # Setup mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        service = EmailService()
        result = service.send_cv_request_notification(
            name="John Doe",
            email="john@example.com",
            company="Test Corp",
            message="Please send CV",
        )

        self.assertTrue(result)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_with("user@example.com", "password")
        mock_server.send_message.assert_called_once()

        # Verify message content roughly
        args, _ = mock_server.send_message.call_args
        msg = args[0]
        self.assertEqual(msg["Subject"], "CV Request from John Doe (Test Corp)")

    @patch("app.services.email.settings")
    def test_send_cv_request_missing_config(self, mock_settings):
        mock_settings.smtp_host = ""

        service = EmailService()
        result = service.send_cv_request_notification("Name", "email", "co", "msg")

        self.assertFalse(result)

    @patch("app.services.email.settings")
    @patch("smtplib.SMTP")
    def test_send_cv_request_exception(self, mock_smtp, mock_settings):
        # Setup mock settings
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_user = "user"
        mock_settings.smtp_password = "pw"

        # Setup mock exception
        mock_smtp.side_effect = Exception("Connection failed")

        service = EmailService()
        result = service.send_cv_request_notification("Name", "email", "co", "msg")

        self.assertFalse(result)
