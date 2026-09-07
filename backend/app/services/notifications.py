"""Pluggable owner-notification channels (#263).

The product's promise is "no recruiter contact is ever missed" — and email is
where notifications go to be missed. This registry fans one event out to every
CONFIGURED channel: email stays one channel among several, a Telegram ping
lands on the owner's phone in seconds, and a generic webhook covers
Slack/Discord/Mattermost/ntfy with a single implementation.

Contracts, identical to the email path this generalizes:
- empty config  = the channel is absent from the registry; zero requests.
- one dead channel never blocks another, and none ever blocks intake — the
  caller already runs in a background task whose wrapper swallows everything.

WhatsApp is a DOCUMENTED DECISION, not a stub: the Business Cloud API needs a
Meta-verified business, template pre-approval, and bills per conversation, so
the adapter is deferred until an owner actually wants it. The seam makes it
one class implementing `NotificationChannel`; nothing here pretends it exists.
"""

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import settings
from app.logger import logger
from app.services.email import EmailService


@dataclass(frozen=True)
class OwnerNotification:
    """One owner-facing event, channel-agnostic. Frozen: an event that has
    fanned out must read identically on every channel."""

    source: str
    name: str
    email: str
    company: str
    message: str

    @classmethod
    def build(
        cls,
        *,
        source: str,
        name: str,
        email: str,
        company: str | None,
        message: str,
    ) -> "OwnerNotification":
        return cls(
            source=source,
            name=name,
            email=email,
            company=company or "",
            message=message,
        )

    def summary(self) -> str:
        """Compact single-message rendering for chat-shaped channels — RAW.
        Escaping is a PER-CHANNEL concern: Slack parses mrkdwn, Telegram's
        plain sendMessage parses nothing, so escaping here showed the owner
        `&amp;`-noise on Telegram while STILL leaking via name/company on
        Slack (#297 round 3 — the escape lived at the wrong layer AND only
        covered one of three attacker-reachable fields)."""
        safe = self.message[:500]
        company = f" ({self.company})" if self.company else ""
        return (
            f"[{self.source}] New interaction from {self.name}{company}\n"
            f"{self.email}\n\n"
            f"{safe}\n\n"
            f"Review: {settings.site_url.rstrip('/')}/admin → Inbox"
        )


class NotificationChannel(Protocol):
    name: str

    def send(
        self, event: OwnerNotification
    ) -> bool: ...  # pragma: no cover — typing Protocol, never executed


class EmailChannel:
    """The pre-existing email path, unchanged, behind the registry seam."""

    name = "email"

    def send(self, event: OwnerNotification) -> bool:
        return EmailService().send_interaction_notification(
            source=event.source,
            name=event.name,
            email=event.email,
            company=event.company,
            message=event.message,
        )


class TelegramChannel:
    """Telegram Bot API — free, self-serve (@BotFather), two env vars.

    Rule 10: the API is free but still external; tests mock the httpx
    boundary and CI never holds a real token (empty config = channel off,
    exactly like SMTP).
    """

    name = "telegram"

    def send(self, event: OwnerNotification) -> bool:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        try:
            response = httpx.post(
                url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": event.summary(),
                },
                timeout=settings.notify_timeout_seconds,
            )
            response.raise_for_status()
            logger.info("Telegram notification sent")
            return True
        except Exception as e:
            # The token is PART OF THE URL — never echo the exception's request
            # context wholesale into logs on this channel.
            logger.error(f"Telegram notification failed: {type(e).__name__}")
            return False


class WebhookChannel:
    """Provider-agnostic JSON POST — one implementation covers Slack-style
    incoming webhooks, Discord, Mattermost, ntfy and anything similar."""

    name = "webhook"

    @staticmethod
    def _escape_mrkdwn(text: str) -> str:
        """Slack's documented escaping (&, <, > — & first): submitter text
        from the PUBLIC contact form lands in the mrkdwn-parsed `text`, and
        every field the visitor controls — name, company, message — rides in
        the rendered summary, so the WHOLE string is escaped at this one
        point (#297 round 3: escaping message alone left `<!channel>` in
        `name` delivered verbatim)."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def send(self, event: OwnerNotification) -> bool:
        try:
            response = httpx.post(
                settings.notify_webhook_url,
                json={
                    # `text` is the lingua franca (Slack/Mattermost render it
                    # directly); the structured fields ride alongside for
                    # anything smarter.
                    "text": self._escape_mrkdwn(event.summary()),
                    "source": event.source,
                    "name": event.name,
                    "email": event.email,
                    "company": event.company,
                    "message": event.message,
                },
                timeout=settings.notify_timeout_seconds,
            )
            response.raise_for_status()
            logger.info("Webhook notification sent")
            return True
        except Exception as e:
            logger.error(f"Webhook notification failed: {type(e).__name__}")
            return False


def configured_channels() -> list[NotificationChannel]:
    """Registry built FRESH per call, from live settings: a channel exists
    exactly when its config does. (Fresh, not cached at import — tests and a
    future admin settings UI both change config at runtime.)"""
    channels: list[NotificationChannel] = []
    if settings.smtp_host:
        channels.append(EmailChannel())
    if settings.telegram_bot_token and settings.telegram_chat_id:
        channels.append(TelegramChannel())
    if settings.notify_webhook_url:
        channels.append(WebhookChannel())
    return channels


def notify_owner(event: OwnerNotification) -> dict[str, bool]:
    """Fan out to every configured channel; each failure isolated. Returns
    per-channel outcomes (for logs/tests — callers must not gate on it)."""
    results: dict[str, bool] = {}
    for channel in configured_channels():
        try:
            results[channel.name] = channel.send(event)
        except Exception as e:  # a channel that RAISES is still just False
            logger.error(f"{channel.name} channel raised: {type(e).__name__}")
            results[channel.name] = False
    return results
