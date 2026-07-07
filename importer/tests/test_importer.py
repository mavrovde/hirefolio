"""Tests for the standalone importer (spec 06). Mocked HTTP — no live LinkedIn/prod."""

import json
from pathlib import Path

import httpx

from importer import core
from importer.core import (
    Config,
    Ledger,
    detect_language,
    load_posts,
    post_fingerprint,
    run,
)

POSTS = [
    {
        "urn": "urn:li:activity:2",
        "content": "Newer post about engineering.",
        "imageUrl": "https://media.licdn.com/dms/image/post2.jpg",
        "imageUrls": ["https://media.licdn.com/dms/image/post2.jpg"],
        "postedAt": "2026-07-05T10:00:00Z",
        "url": "https://www.linkedin.com/feed/update/urn:li:activity:2/",
        "language": "en",
    },
    {
        "urn": "urn:li:activity:1",
        "content": "Older post, no image.",
        "postedAt": "2026-07-01T10:00:00Z",
        "url": "https://www.linkedin.com/feed/update/urn:li:activity:1/",
    },
]


def _cfg(tmp_path: Path, posts=POSTS, **over) -> Config:
    pj = tmp_path / "posts_data.json"
    pj.write_text(json.dumps(posts))
    return Config(
        api_url="http://test",
        token="tok",
        posts_json=pj,
        state_path=tmp_path / "state.json",
        backoff=0.0,
        retries=2,
        **over,
    )


def _transport(status=200, created=True):
    calls = {"posts": [], "images": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/import-post"):
            calls["posts"].append(str(request.url))
            if status >= 500:
                return httpx.Response(status, text="server error")
            return httpx.Response(
                200, json={"id": len(calls["posts"]), "slug": "s", "created": created}
            )
        calls["images"].append(str(request.url))
        return httpx.Response(
            200, content=b"IMGBYTES", headers={"content-type": "image/jpeg"}
        )

    return httpx.MockTransport(handler), calls


# --- unit ------------------------------------------------------------------


def test_detect_language():
    assert detect_language("Das ist für mich nicht gut") == "de"
    assert detect_language("This is english") == "en"
    assert detect_language("", default="en") == "en"


def test_fingerprint_stable_and_content_sensitive():
    a = {"content": "x", "imageUrl": "u", "imageUrls": ["u"]}
    assert post_fingerprint(a) == post_fingerprint(dict(a))
    assert post_fingerprint(a) != post_fingerprint({**a, "content": "y"})


def test_load_posts_sorts_oldest_first_and_drops_empty(tmp_path):
    posts = POSTS + [{"urn": "x", "content": "  "}]  # empty content dropped
    cfg = _cfg(tmp_path, posts=posts)
    loaded = load_posts(cfg)
    assert [p["urn"] for p in loaded] == ["urn:li:activity:1", "urn:li:activity:2"]


def test_ledger_roundtrip(tmp_path):
    led = Ledger(tmp_path / "s.json")
    assert not led.unchanged("u", "fp")
    led.mark("u", "fp")
    led.save()
    assert Ledger(tmp_path / "s.json").unchanged("u", "fp")


# --- run -------------------------------------------------------------------


def test_run_imports_each_post_once(tmp_path):
    transport, calls = _transport()
    with httpx.Client(transport=transport) as client:
        summary = run(_cfg(tmp_path), client=client)
    assert summary.created == 2 and summary.failed == 0
    assert len(calls["posts"]) == 2
    assert len(calls["images"]) == 1  # only the post that had an imageUrl


def test_retry_then_failed_continues(tmp_path):
    transport, calls = _transport(status=500)
    with httpx.Client(transport=transport) as client:
        summary = run(_cfg(tmp_path), client=client)
    # every post retried `retries` times, batch still completes, reported as failed
    assert summary.failed == 2 and summary.ok is False
    assert len(calls["posts"]) == 2 * 2  # 2 posts × 2 attempts


def test_idempotent_second_run(tmp_path):
    cfg = _cfg(tmp_path)
    transport, calls = _transport()
    with httpx.Client(transport=transport) as client:
        run(cfg, client=client)
    first = len(calls["posts"])
    # second run over the same input + persisted ledger imports nothing new
    with httpx.Client(transport=transport) as client:
        summary2 = run(cfg, client=client)
    assert first == 2
    assert len(calls["posts"]) == first  # no new POSTs
    assert summary2.skipped == 2 and summary2.created == 0


def test_dry_run_posts_nothing(tmp_path):
    transport, calls = _transport()
    with httpx.Client(transport=transport) as client:
        summary = run(_cfg(tmp_path, dry_run=True), client=client)
    assert calls["posts"] == [] and calls["images"] == []
    assert summary.skipped == 2
    assert not (tmp_path / "state.json").exists()  # ledger not written on dry-run


def test_publish_flag_sends_true(tmp_path):
    seen = {}

    def handler(request):
        if request.url.path.endswith("/import-post"):
            seen["published"] = (
                b'name="published"\r\n\r\ntrue' in request.content
                or b"published=true" in request.content
            )
            return httpx.Response(200, json={"created": True})
        return httpx.Response(200, content=b"x", headers={"content-type": "image/jpeg"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        run(_cfg(tmp_path, posts=[POSTS[1]], publish=True), client=client)
    assert seen.get("published") is True


# --- independence guard ----------------------------------------------------


def test_importer_has_no_agents_dependency():
    import re

    root = Path(core.__file__).resolve().parent
    pat = re.compile(r"^\s*(import agents|from agents)\b", re.M)
    for py in root.rglob("*.py"):
        if "tests" in py.parts:  # don't scan the test files themselves
            continue
        assert not pat.search(py.read_text()), py
