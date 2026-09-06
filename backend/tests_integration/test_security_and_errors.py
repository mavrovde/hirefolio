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


def test_promote_is_idempotent_through_the_real_stack(
    client: httpx.Client, admin_token: str
):
    """#279 through real HTTP: the composed stack must return the SAME card for
    a repeated promote — the unit test proves the handler, this proves the
    contract survives serialization, the proxy and the session boundary."""
    marker = f"idem-{uuid.uuid4().hex[:12]}"
    created = client.post(
        f"{API}/interactions/contact",
        json={
            "name": "Idem Prober",
            "email": f"{marker}@integration.example",
            "company": "Idem GmbH",
            "message": f"Idempotency probe {marker} through the composed stack.",
        },
    )
    assert created.status_code == 201, created.text
    interaction_id = created.json()["id"]
    auth = {"Authorization": f"Bearer {admin_token}"}

    first = client.post(
        f"{API}/admin/opportunities/promote",
        json={"interaction_id": interaction_id},
        headers=auth,
    )
    second = client.post(
        f"{API}/admin/opportunities/promote",
        json={"interaction_id": interaction_id},
        headers=auth,
    )
    assert first.status_code == 201 and second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    # And exactly one card carries this recruiter — no duplicate on the board.
    board = client.get(f"{API}/admin/opportunities", headers=auth)
    assert board.status_code == 200
    mine = [
        o
        for o in board.json()["items"]
        if o["recruiter_email"] == f"{marker}@integration.example"
    ]
    assert len(mine) == 1


def test_promoted_cv_request_keeps_its_origin(client: httpx.Client, admin_token: str):
    """#278 through the real stack: a cv_request promoted to the pipeline must
    NOT be relabelled as recruiter outreach — the funnel dimension (#249)
    depends on the origin surviving promotion."""
    auth = {"Authorization": f"Bearer {admin_token}"}
    inbox = client.get(
        f"{API}/admin/interactions", params={"source": "cv_request"}, headers=auth
    )
    assert inbox.status_code == 200
    items = inbox.json()["items"]
    if not items:
        # No CV request in this stack run — request one so the case is real.
        req = client.post(
            f"{API}/cv/request",
            json={
                "name": "CV Prober",
                "email": f"cv-{uuid.uuid4().hex[:10]}@integration.example",
                "company": "Prober GmbH",
                "position_description": "Staff Engineer",
                "message": "Please share your CV.",
            },
        )
        # Deliberately an ASSERT, not a skip: the stack's seed creates an active
        # CV document, so this endpoint is always available here — a skip would
        # silently mask the regression this test exists to catch (review finding).
        assert req.status_code in (200, 201), (
            f"CV request failed ({req.status_code}); the seeded stack should "
            f"accept it: {req.text}"
        )
        inbox = client.get(
            f"{API}/admin/interactions", params={"source": "cv_request"}, headers=auth
        )
        items = inbox.json()["items"]
        assert items, "a cv_request interaction should exist after requesting a CV"

    promoted = client.post(
        f"{API}/admin/opportunities/promote",
        json={"interaction_id": items[0]["id"]},
        headers=auth,
    )
    assert promoted.status_code == 201, promoted.text
    assert promoted.json()["source"] == "discovery"
