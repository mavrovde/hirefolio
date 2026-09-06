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

            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as server:
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

            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info(f"Requester confirmation sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send confirmation email to {email}: {e}")
            return False

    def send_interview_reminder(
        self,
        *,
        company: str,
        role_title: str,
        kind: str,
        scheduled_at_iso: str,
        duration_minutes: int,
        location_or_link: str | None,
        interviewer: str | None,
        ics_payload: str,
        rescheduled: bool = False,
    ) -> bool:
        """Owner-facing interview reminder with the event's `.ics` attached.

        #247 criterion 3: "the owner gets a reminder email via existing SMTP
        (skipped gracefully when SMTP is unconfigured)". Sent at scheduling
        (and RE-scheduling) time with the invite attached — the calendar app
        the owner imports it into carries the actual time-based alarm; this
        repo deliberately has no scheduler process to fire one later.
        """
        if (
            not settings.smtp_host
            or not settings.smtp_user
            or not settings.smtp_password
        ):
            logger.warning("Email configuration missing. Skipping email sending.")
            return False

        try:
            verb = "rescheduled" if rescheduled else "scheduled"
            msg = EmailMessage()
            msg.set_content(f"""
Interview {verb}!

Details:
--------------------------------
Company: {company}
Role: {role_title}
Kind: {kind}
When: {scheduled_at_iso} ({duration_minutes} min)
Where: {location_or_link or "N/A"}
Interviewer: {interviewer or "N/A"}
--------------------------------

The invite is attached — import it into your calendar for a timed reminder.
""")
            msg["Subject"] = (
                f"Interview {verb}: {role_title} at {company} — {scheduled_at_iso}"
            )
            msg["From"] = settings.smtp_user
            msg["To"] = settings.admin_email
            msg.add_attachment(
                ics_payload.encode("utf-8"),
                maintype="text",
                subtype="calendar",
                filename="interview.ics",
                # RFC 2046 defaults text/* to us-ascii; the payload is UTF-8
                # (company names, interviewer names), and the export route
                # already declares charset=utf-8 — the attachment must match.
                params={"charset": "utf-8"},
            )

            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info(f"Interview reminder sent to {settings.admin_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
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

            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info(f"Interaction notification sent to {settings.admin_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send interaction notification: {e}")
            return False


email_service = EmailService()
