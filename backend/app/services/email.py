import smtplib
from email.message import EmailMessage

from app.config import settings
from app.logger import logger


class EmailService:
    def _configured(self) -> bool:
        """Sending is gated on smtp_host ALONE (#262): a local catch-all like
        Mailpit needs neither credentials nor STARTTLS, so requiring user and
        password would keep dev/E2E email permanently off. External providers
        still get auth + STARTTLS because those settings default on."""
        if not settings.smtp_host:
            logger.warning("Email configuration missing. Skipping email sending.")
            return False
        return True

    def _from_address(self) -> str:
        """A no-auth relay has no smtp_user to borrow the From from."""
        return settings.smtp_from or settings.smtp_user or "hirefolio@localhost"

    def _send(self, msg: EmailMessage, success_log: str) -> bool:
        """The ONE SMTP transport — it was quadruplicated across every method,
        which is how a STARTTLS flag would have needed four edits and missed
        one. STARTTLS and login are independent and each optional (#262);
        every connection stays time-bounded (#69 review)."""
        try:
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as server:
                if settings.smtp_starttls:
                    server.starttls()
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
            logger.info(success_log)
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_cv_request_notification(
        self,
        name: str,
        email: str,
        company: str,
        message: str,
        position_description: str | None = None,
        subscribe_to_updates: bool = False,
    ):
        if not self._configured():
            return False

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
        msg["From"] = self._from_address()
        msg["To"] = settings.admin_email

        return self._send(msg, f"CV Request email sent to {settings.admin_email}")

    def send_requester_confirmation(self, name: str, email: str):
        if not self._configured():
            return False

        msg = EmailMessage()
        msg.set_content(f"""
Hello {name},

This is an automated confirmation that your request for {settings.owner_name}'s CV has been received.

If you weren't able to download it immediately, you can try again later or respond to this email.

Best regards,
{settings.owner_name}
""")
        msg["Subject"] = f"CV Request Confirmation - {settings.owner_name}"
        msg["From"] = self._from_address()
        msg["To"] = email

        return self._send(msg, f"Requester confirmation sent to {email}")

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
        if not self._configured():
            return False

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
        msg["From"] = self._from_address()
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

        return self._send(msg, f"Interview reminder sent to {settings.admin_email}")

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
        if not self._configured():
            return False

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
        msg["From"] = self._from_address()
        msg["To"] = settings.admin_email

        return self._send(
            msg, f"Interaction notification sent to {settings.admin_email}"
        )


email_service = EmailService()
