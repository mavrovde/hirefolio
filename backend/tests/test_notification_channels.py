"""Pluggable notification channels (#263), pinned criterion by criterion.

Rule 10 throughout: every HTTP boundary is mocked; no test can reach Telegram
or any webhook — empty config disables a channel exactly like SMTP, and the
empty-config tests assert ZERO requests, not just "no failure".
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.notifications import (
    OwnerNotification,
    configured_channels,
    notify_owner,
)

EVENT = OwnerNotification(
    source="contact_form",
    name="Rita Recruiter",
    email="rita@agency.example",
    company="Agency GmbH",
    message="Are you available for a Staff role?",
)


def _cfg(**overrides):
    defaults = {
        "smtp_host": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "notify_webhook_url": "",
    }
    defaults.update(overrides)
    return [patch(f"app.config.settings.{k}", v) for k, v in defaults.items()]


def _with(patches, fn):
    for c in patches:
        c.start()
    try:
        return fn()
    finally:
        for c in patches:
            c.stop()


# ---------------------------------------------------------------- registry --


def test_empty_config_means_empty_registry_and_zero_requests():
    with patch("app.services.notifications.httpx.post") as post:
        result = _with(_cfg(), lambda: notify_owner(EVENT))
        assert result == {}
        post.assert_not_called()


def test_channels_register_exactly_when_their_config_is_present():
    assert _with(
        _cfg(smtp_host="mailpit"), lambda: [c.name for c in configured_channels()]
    ) == ["email"]
    assert _with(
        _cfg(telegram_bot_token="t", telegram_chat_id="c"),
        lambda: [c.name for c in configured_channels()],
    ) == ["telegram"]
    assert _with(
        _cfg(notify_webhook_url="https://hooks.example/x"),
        lambda: [c.name for c in configured_channels()],
    ) == ["webhook"]
    # Half a Telegram config is NO Telegram config.
    assert (
        _with(
            _cfg(telegram_bot_token="t"),
            lambda: [c.name for c in configured_channels()],
        )
        == []
    )


# ---------------------------------------------------------------- telegram --


def test_telegram_posts_the_bot_api_with_chat_id_and_summary():
    with patch("app.services.notifications.httpx.post") as post:
        post.return_value = MagicMock(raise_for_status=lambda: None)
        result = _with(
            _cfg(telegram_bot_token="123:abc", telegram_chat_id="42"),
            lambda: notify_owner(EVENT),
        )
    assert result == {"telegram": True}
    url = post.call_args.args[0]
    assert url == "https://api.telegram.org/bot123:abc/sendMessage"
    payload = post.call_args.kwargs["json"]
    assert payload["chat_id"] == "42"
    assert "[contact_form] New interaction from Rita Recruiter" in payload["text"]
    assert "admin" in payload["text"]  # the deep link back to the inbox
    assert post.call_args.kwargs["timeout"] == settings.notify_timeout_seconds


def test_telegram_failure_is_false_and_never_leaks_the_token_into_logs():
    import httpx as real_httpx

    with patch("app.services.notifications.httpx.post") as post:
        post.side_effect = real_httpx.ConnectError(
            "boom https://api.telegram.org/botSECRET-TOKEN/sendMessage"
        )
        with patch("app.services.notifications.logger") as log:
            result = _with(
                _cfg(telegram_bot_token="SECRET-TOKEN", telegram_chat_id="42"),
                lambda: notify_owner(EVENT),
            )
    assert result == {"telegram": False}
    # The token is part of the URL; the log line must carry the exception TYPE
    # only, never its message (pinned — this is why the except logs __name__).
    logged = " ".join(str(c) for c in log.error.call_args_list)
    assert "SECRET-TOKEN" not in logged


def test_httpx_success_logging_never_carries_the_token(caplog):
    """#297 review blocker 2: httpx logs every request URL at INFO — and the
    Bot API URL CONTAINS the token, so a SUCCESSFUL send printed the
    credential into container logs. The first leak test was structurally
    blind: it mocked httpx.post (so httpx never logged) and asserted a mocked
    logger. This one routes through a REAL httpx client over MockTransport,
    so httpx's own logging pipeline runs for real."""
    import logging

    import httpx as real_httpx

    def through_real_client(url, **kwargs):
        transport = real_httpx.MockTransport(
            lambda request: real_httpx.Response(200, json={"ok": True})
        )
        with real_httpx.Client(transport=transport) as c:
            return c.post(url, json=kwargs.get("json"))

    with (
        patch("app.services.notifications.httpx.post", side_effect=through_real_client),
        caplog.at_level(logging.DEBUG),
    ):
        result = _with(
            _cfg(telegram_bot_token="SECRET-TOKEN-42", telegram_chat_id="7"),
            lambda: notify_owner(EVENT),
        )
    assert result == {"telegram": True}
    assert "SECRET-TOKEN-42" not in caplog.text


def test_telegram_http_500_is_a_failure_not_a_success():
    """AC2's own words. raise_for_status is the ONLY thing turning a 4xx/5xx
    into False here — deleting it left the suite green (#297 review major 5),
    so this pins it: a well-formed 500 response, no exception from post()."""
    import httpx as real_httpx

    response = real_httpx.Response(
        500,
        request=real_httpx.Request("POST", "https://api.telegram.org/botX/sendMessage"),
    )
    with patch("app.services.notifications.httpx.post", return_value=response):
        result = _with(
            _cfg(telegram_bot_token="t", telegram_chat_id="c"),
            lambda: notify_owner(EVENT),
        )
    assert result == {"telegram": False}


# ----------------------------------------------------------------- webhook --


def test_webhook_posts_slack_style_text_plus_structured_fields():
    with patch("app.services.notifications.httpx.post") as post:
        post.return_value = MagicMock(raise_for_status=lambda: None)
        result = _with(
            _cfg(notify_webhook_url="https://hooks.slack.example/T/B/x"),
            lambda: notify_owner(EVENT),
        )
    assert result == {"webhook": True}
    assert post.call_args.args[0] == "https://hooks.slack.example/T/B/x"
    # The timeout is load-bearing (#207): deleting it left the suite green
    # (#297 review major 6).
    assert post.call_args.kwargs["timeout"] == settings.notify_timeout_seconds
    payload = post.call_args.kwargs["json"]
    assert "New interaction from Rita Recruiter" in payload["text"]
    assert payload["source"] == "contact_form"
    assert payload["email"] == "rita@agency.example"


def test_webhook_http_500_is_a_failure_not_a_success():
    import httpx as real_httpx

    response = real_httpx.Response(
        500, request=real_httpx.Request("POST", "https://hooks.example/x")
    )
    with patch("app.services.notifications.httpx.post", return_value=response):
        result = _with(
            _cfg(notify_webhook_url="https://hooks.example/x"),
            lambda: notify_owner(EVENT),
        )
    assert result == {"webhook": False}


def test_webhook_failure_is_false_and_logs_the_type_only():
    import httpx as real_httpx

    with patch("app.services.notifications.httpx.post") as post:
        post.side_effect = real_httpx.ConnectError("refused")
        result = _with(
            _cfg(notify_webhook_url="https://hooks.example/x"),
            lambda: notify_owner(EVENT),
        )
    assert result == {"webhook": False}


# ---------------------------------------------------------------- fan-out ---


def test_one_dead_channel_never_blocks_another():
    """Telegram 500s; the webhook must still fire and succeed."""
    import httpx as real_httpx

    calls = []

    def post(url, **kwargs):
        calls.append(url)
        if "telegram" in url:
            raise real_httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
        return MagicMock(raise_for_status=lambda: None)

    with patch("app.services.notifications.httpx.post", side_effect=post):
        result = _with(
            _cfg(
                telegram_bot_token="t",
                telegram_chat_id="c",
                notify_webhook_url="https://hooks.example/x",
            ),
            lambda: notify_owner(EVENT),
        )
    assert result == {"telegram": False, "webhook": True}
    assert len(calls) == 2


def test_a_channel_that_raises_outside_its_own_handling_is_isolated():
    """Even a channel whose send() itself raises (not just fails) must not
    stop the fan-out — the registry's own belt to the channels' braces."""
    from app.services import notifications as n

    class Bomb:
        name = "bomb"

        def send(self, event):
            raise RuntimeError("kaboom")

    ok = MagicMock()
    ok.name = "ok"
    ok.send.return_value = True
    with patch.object(n, "configured_channels", return_value=[Bomb(), ok]):
        result = n.notify_owner(EVENT)
    assert result == {"bomb": False, "ok": True}
    ok.send.assert_called_once()


# ------------------------------------------------------------- end to end ---


@pytest.mark.asyncio
async def test_contact_form_fans_out_through_the_registry(client: AsyncClient):
    """The #69 call site goes through the registry: with Telegram AND email
    configured, one submission produces both — through mocked boundaries."""
    sent = {"email": 0, "telegram": 0}

    def fake_email(self, **kwargs):
        sent["email"] += 1
        return True

    def fake_post(url, **kwargs):
        assert url.startswith("https://api.telegram.org/bot")
        sent["telegram"] += 1
        return MagicMock(raise_for_status=lambda: None)

    from app.services.email import EmailService

    with (
        patch.object(EmailService, "send_interaction_notification", fake_email),
        patch("app.services.notifications.httpx.post", side_effect=fake_post),
        patch("app.config.settings.smtp_host", "mailpit"),
        patch("app.config.settings.telegram_bot_token", "t"),
        patch("app.config.settings.telegram_chat_id", "c"),
    ):
        r = await client.post(
            f"{settings.api_prefix}/interactions/contact",
            json={
                "name": "Fanout Probe",
                "email": "probe@example.com",
                "message": "Testing the notification registry fan-out.",
            },
        )
        assert r.status_code == 201
    assert sent == {"email": 1, "telegram": 1}


# ---------------------------------------------------------------- summary ----


def test_summary_truncates_long_messages_and_escapes_mrkdwn():
    """The two executed-but-unasserted branches (#297 review minors) plus the
    injection fix: 500-char truncation, the empty-company arm, and Slack
    mrkdwn escaping — a visitor must not be able to smuggle <!channel> into
    the owner's Slack."""
    long_event = OwnerNotification.build(
        source="contact_form",
        name="N",
        email="n@example.com",
        company=None,
        message="x" * 600,
    )
    text = long_event.summary()
    assert "x" * 500 in text and "x" * 501 not in text
    assert "(" not in text.split("\n")[0]  # empty company renders no parens

    inject = OwnerNotification.build(
        source="contact_form",
        name="N",
        email="n@example.com",
        company="ACME",
        message="hi <!channel> & <http://evil.example|click>",
    )
    text = inject.summary()
    assert "<!channel>" not in text
    assert "&lt;!channel&gt;" in text
    assert "&amp;" in text


# -------------------------------------------------------------- namespacing --


def test_hirefolio_namespaced_env_binds_and_generic_does_not(monkeypatch):
    """#141's contract, tested per the gemini-env precedent: the credential
    binds ONLY through its HIREFOLIO_* name; the generic name is ignored."""
    from app.config import Settings

    monkeypatch.setenv("HIREFOLIO_TELEGRAM_BOT_TOKEN", "ns-token")
    monkeypatch.setenv("HIREFOLIO_TELEGRAM_CHAT_ID", "ns-chat")
    monkeypatch.setenv("HIREFOLIO_NOTIFY_WEBHOOK_URL", "https://ns.example/w")
    fresh = Settings()
    assert fresh.telegram_bot_token == "ns-token"
    assert fresh.telegram_chat_id == "ns-chat"
    assert fresh.notify_webhook_url == "https://ns.example/w"

    monkeypatch.delenv("HIREFOLIO_TELEGRAM_BOT_TOKEN")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "generic-must-not-bind")
    assert Settings().telegram_bot_token == ""
