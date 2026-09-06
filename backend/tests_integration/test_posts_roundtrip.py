"""Post lifecycle across the composed stack — including the pgvector path.

Creating a post triggers a REAL embeddings call (backend → WireMock's
/api/embeddings stub, fixed 768-dim vector), and semantic search embeds the
query the same way — so this exercises HTTP, DB, and pgvector together with
zero mocking inside the backend process.
"""

import uuid

import httpx

from conftest import API


def test_post_create_read_search_delete(client: httpx.Client, admin_headers):
    marker = uuid.uuid4().hex[:12]
    title = f"Integration probe {marker}"

    created = client.post(
        f"{API}/posts",
        headers=admin_headers,
        json={
            "title": title,
            "slug": f"integration-probe-{marker}",
            "content": f"Deterministic integration-tier content {marker}. "
            "The embedding for this text comes from WireMock.",
            "language": "en",
            "published": True,
            "tags": ["integration"],
        },
    )
    assert created.status_code in (200, 201), created.text
    post = created.json()
    post_id, slug = post["id"], post["slug"]

    try:
        # public list sees it
        listed = client.get(f"{API}/posts", params={"page_size": 50}).json()
        assert any(p["id"] == post_id for p in listed["items"])

        # slug fetch works through the same public surface
        by_slug = client.get(f"{API}/posts/{slug}")
        assert by_slug.status_code == 200
        assert by_slug.json()["title"] == title

        # semantic search embeds the query via WireMock and answers 200.
        # Every stored vector is identical (fixed stub), so ranking is
        # meaningless — the assertion is that the pgvector path WORKS,
        # not that it ranks.
        search = client.get(f"{API}/posts/search/semantic", params={"q": marker})
        assert search.status_code == 200
    finally:
        deleted = client.delete(f"{API}/posts/{post_id}", headers=admin_headers)
        assert deleted.status_code in (200, 204)
