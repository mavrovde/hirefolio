"""Composition-sensitive security and error paths (#261 review round 1).

These are the scenarios the reviewer flagged as the tier's missing middle:
the authz boundary, the 404 class (#108 regressions), CORS through the real
middleware stack, i18n parameter handling, and the #69 contact-form →
admin-inbox round trip — the newest public WRITE path in the product.
"""

import uuid

import httpx

from conftest import API


def test_admin_write_rejects_anonymous_callers(client: httpx.Client):
    """POST /posts is admin-gated — an unauthenticated create must be refused
    by the composed stack (401; FastAPI's OAuth2 dependency contract)."""
    resp = client.post(f"{API}/posts", json={"title": "nope", "content": "nope"})
    assert resp.status_code == 401


def test_unknown_slug_is_a_clean_404(client: httpx.Client):
    resp = client.get(f"{API}/posts/definitely-not-a-real-slug-xyz")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_cors_preflight_allows_the_configured_origin(client: httpx.Client):
    """The CORS allowlist must survive composition (env → settings → middleware).
    http://localhost:4200 is in the default `cors_origins` allowlist."""
    resp = client.request(
        "OPTIONS",
        f"{API}/posts",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:4200"


def test_profile_accepts_the_de_locale_parameter(client: httpx.Client):
    """i18n param routing: ?lang=de must be accepted by the composed stack.
    Contract: 200 with the uploaded profile, or 404 on a fresh stack (the
    documented never-blank fallback — the frontend then serves its bundled
    asset). Anything else (422, 500) is a composition regression."""
    resp = client.get(f"{API}/profile", params={"lang": "de"})
    assert resp.status_code in (200, 404)
    assert resp.json()  # parses either way (profile dict or detail)


def test_contact_form_lands_in_the_admin_inbox(client: httpx.Client, admin_token: str):
    """#69 round trip through the real stack: the public write (rate-limited,
    validated, normalized) must surface in the admin inbox with the right
    source and status — the tier's headline composition case."""
    marker = f"it-{uuid.uuid4().hex[:12]}"
    resp = client.post(
        f"{API}/interactions/contact",
        json={
            "name": "Integration Prober",
            "email": f"{marker}@integration.example",
            "company": "Tier Two GmbH",
            "message": f"Round-trip probe {marker} through the composed stack.",
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["source"] == "contact_form"
    assert created["status"] == "new"

    inbox = client.get(
        f"{API}/admin/interactions",
        params={"source": "contact_form"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert inbox.status_code == 200
    emails = [item["email"] for item in inbox.json()["items"]]
    assert f"{marker}@integration.example" in emails
