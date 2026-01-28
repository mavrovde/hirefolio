import smtplib
from email.message import EmailMessage
from app.config import settings
from app.logger import logger

class EmailService:
    def send_cv_request_notification(self, name: str, email: str, company: str, message: str):
        if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
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
--------------------------------

Please review and respond if necessary.
""")

            msg['Subject'] = f"CV Request from {name} ({company})"
            msg['From'] = settings.smtp_user
            msg['To'] = settings.admin_email

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
            
            logger.info(f"CV Request email sent to {settings.admin_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

email_service = EmailService()
