"""End-to-end email through the bundled Mailpit catch-all (#262).

The FIRST real email assertion in the repo: every earlier layer stops at the
`smtplib` boundary (rule 10 — no test may talk to a paid relay). Mailpit
delivers nothing externally, so the whole path — HTTP request → background
task → SMTP over the compose network → captured message — is finally
observable. If the mail flow breaks anywhere along it, THIS fails.
"""

import os
import time
import uuid

import httpx

MAILPIT_URL = os.environ.get("MAILPIT_URL", "http://localhost:8025").rstrip("/")


def _search(client: httpx.Client, query: str) -> list[dict]:
    r = client.get(f"{MAILPIT_URL}/api/v1/search", params={"query": query})
    assert r.status_code == 200, r.text
    return r.json().get("messages") or []


def test_contact_form_notification_lands_in_mailpit(client: httpx.Client):
    from conftest import API

    marker = f"mp-{uuid.uuid4().hex[:10]}"

    # RATE-LIMIT BUDGET (#296 round 2): the contact endpoint allows 5/60s and
    # the whole tier currently posts 3 contacts, so the gating run has a
    # headroom of two — an invariant WRITTEN DOWN here because nothing else
    # enforces it. The retry keeps a manual re-run (or a future fourth poster)
    # from failing on 429 instead of on the mail path.
    submitted = None
    for _ in range(3):
        submitted = client.post(
            f"{API}/interactions/contact",
            json={
                "name": f"Mailpit Probe {marker}",
                "email": "probe@example.com",
                "message": f"Integration probe {marker}: does the owner get mail?",
            },
        )
        if submitted.status_code != 429:
            break
        time.sleep(21)  # a third of the window frees a slot
    assert submitted is not None and submitted.status_code == 201, submitted.text

    # The notification rides a background task + real SMTP hop; poll briefly
    # rather than sleeping a fixed worst case.
    found: list[dict] = []
    for _ in range(20):
        found = _search(client, marker)
        if found:
            break
        time.sleep(0.5)
    assert found, (
        f"no message containing {marker!r} reached Mailpit within 10s — "
        "the notification path is broken somewhere between the endpoint "
        "and SMTP"
    )
    subject = found[0]["Subject"]
    assert "contact_form" in subject and "Mailpit Probe" in subject, subject
