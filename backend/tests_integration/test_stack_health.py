"""Composed-system smoke: the stack answers, versions agree, AI boundary is up."""

import re

import httpx

from conftest import API, BACKEND_URL, PUBLIC_URL


def test_backend_health(client: httpx.Client):
    resp = client.get(f"{API}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_root_banner(client: httpx.Client):
    resp = client.get(f"{BACKEND_URL}/")
    assert resp.status_code == 200
    assert "API" in resp.json()["message"]


def test_public_stats_reports_semver(client: httpx.Client):
    data = client.get(f"{API}/stats/public").json()
    assert re.match(r"^\d+\.\d+\.\d+", data["backend_version"])


def test_admin_stats_sees_ai_service_up(client: httpx.Client, admin_headers):
    """The ai_service health flag comes from a real GET against OLLAMA_URL —
    with the inttest overlay that is WireMock's root stub, so a True here
    proves the backend↔AI-boundary wiring end to end."""
    resp = client.get(f"{API}/stats", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["system_health"]["ai_service"] is True


def test_public_site_through_proxy(client: httpx.Client):
    """The reverse proxy serves the SSR app and routes /api/* to the backend."""
    page = client.get(f"{PUBLIC_URL}/", headers={"Host": "localhost"})
    assert page.status_code == 200
    api = client.get(f"{PUBLIC_URL}/api/app/health", headers={"Host": "localhost"})
    assert api.status_code == 200
