import smtplib
from email.message import EmailMessage

from app.config import settings
from app.logger import logger


class EmailService:
    def send_cv_request_notification(
        self,
        name: str,
        email: str,
        company: str,
        message: str,
        position_description: str | None = None,
        subscribe_to_updates: bool = False,
    ):
        if (
            not settings.smtp_host
            or not settings.smtp_user
            or not settings.smtp_password
        ):
            logger.warning("Email configuration missing. Skipping email sending.")
            return False

        try:
            msg = EmailMessage()
            msg.set_content(f"""
New CV Request received!

Details:
--------------------------------
Name: {name}
Email: {email}
Company: {company}
Message:
{message}

Position/Project Description:
{position_description or "N/A"}

Subscribed to Updates: {"Yes" if subscribe_to_updates else "No"}
--------------------------------

Please review and respond if necessary.
""")

            msg["Subject"] = f"CV Request from {name} ({company})"
            msg["From"] = settings.smtp_user
            msg["To"] = settings.admin_email

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info(f"CV Request email sent to {settings.admin_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_requester_confirmation(self, name: str, email: str):
        if (
            not settings.smtp_host
            or not settings.smtp_user
            or not settings.smtp_password
        ):
            return False

        try:
            msg = EmailMessage()
            msg.set_content(f"""
Hello {name},

This is an automated confirmation that your request for {settings.owner_name}'s CV has been received.

If you weren't able to download it immediately, you can try again later or respond to this email.

Best regards,
{settings.owner_name}
""")
            msg["Subject"] = f"CV Request Confirmation - {settings.owner_name}"
            msg["From"] = settings.smtp_user
            msg["To"] = email

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info(f"Requester confirmation sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send confirmation email to {email}: {e}")
            return False

    def send_interaction_notification(
        self,
        source: str,
        name: str,
        email: str,
        company: str,
        message: str,
    ) -> bool:
        """Generic new-interaction alert to the owner (#69) — one method for
        every inbox source, same skip-gracefully-when-unconfigured contract as
        the CV-specific notifications above."""
        if (
            not settings.smtp_host
            or not settings.smtp_user
            or not settings.smtp_password
        ):
            logger.warning("Email configuration missing. Skipping email sending.")
            return False

        try:
            msg = EmailMessage()
            msg.set_content(f"""
New interaction in your inbox!

Source: {source}
--------------------------------
Name: {name}
Email: {email}
Company: {company or "N/A"}
Message:
{message}
--------------------------------

Review and update its status in the admin panel.
""")
            msg["Subject"] = f"[{source}] New interaction from {name}"
            msg["From"] = settings.smtp_user
            msg["To"] = settings.admin_email

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info(f"Interaction notification sent to {settings.admin_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send interaction notification: {e}")
            return False


email_service = EmailService()
