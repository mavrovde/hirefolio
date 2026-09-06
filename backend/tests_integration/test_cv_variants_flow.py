"""CV-variant flow over real HTTP on a MIGRATION-BUILT database (#294 rev. 6).

The unit suite runs on a `create_all` schema; this tier is the only place the
cvvar0007-built columns and SET NULL FK serve the composed request path
end-to-end — which is precisely what a migration PR must show.
"""

import uuid

import httpx

from conftest import API


def test_variant_upload_and_record_over_real_http(
    client: httpx.Client, admin_headers: dict[str, str]
):
    marker = uuid.uuid4().hex[:8]

    opportunity = client.post(
        f"{API}/admin/opportunities",
        json={"company": f"Variant GmbH {marker}", "role_title": "Staff Engineer"},
        headers=admin_headers,
    )
    assert opportunity.status_code == 201, opportunity.text
    opp = opportunity.json()
    assert opp["sent_cv_id"] is None

    # What the public flow serves BEFORE the variant upload...
    before = client.get(f"{API}/cv/download")

    upload = client.post(
        f"{API}/admin/cv/upload",
        files={"file": (f"variant-{marker}.pdf", b"%PDF-VARIANT", "application/pdf")},
        data={"version": f"it-{marker}", "activate": "false"},
        headers=admin_headers,
    )
    assert upload.status_code == 200, upload.text

    # ...must be byte-identical after it: the middle clause of #247 criterion 4,
    # proven on the composed stack, not just the unit schema.
    after = client.get(f"{API}/cv/download")
    assert after.status_code == before.status_code
    if before.status_code == 200:
        assert after.content == before.content

    versions = client.get(
        f"{API}/admin/cv/versions",
        params={"page_size": 100, "search": f"it-{marker}"},
        headers=admin_headers,
    ).json()["items"]
    doc = next(v for v in versions if v["version"] == f"it-{marker}")
    assert doc["is_active"] is False

    recorded = client.post(
        f"{API}/admin/opportunities/{opp['id']}/cv-sent",
        json={"cv_document_id": doc["id"]},
        headers=admin_headers,
    )
    assert recorded.status_code == 201, recorded.text

    detail = client.get(
        f"{API}/admin/opportunities/{opp['id']}", headers=admin_headers
    ).json()
    assert detail["sent_cv_id"] == doc["id"]
    assert detail["sent_cv_at"] is not None
    assert any(n["body"].startswith("CV sent:") for n in detail["notes"])
