"""Tests for the public site-config endpoint (#65)."""

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_site_config_returns_all_fields(client: AsyncClient):
    """Every identity field the frontend consumes must be present."""
    response = await client.get(f"{settings.api_prefix}/config/site")
    assert response.status_code == 200
    data = response.json()
    for field in (
        "site_name",
        "site_url",
        "owner_name",
        "owner_headline",
        "owner_description",
        "contact_email",
        "social_links",
        "analytics_id",
    ):
        assert field in data, f"missing field: {field}"


@pytest.mark.asyncio
async def test_site_config_reflects_settings(client: AsyncClient):
    """The payload is derived from Settings, not hardcoded."""
    response = await client.get(f"{settings.api_prefix}/config/site")
    data = response.json()
    assert data["site_name"] == settings.site_name
    assert data["owner_name"] == settings.owner_name
    assert data["owner_headline"] == settings.owner_headline
    assert data["contact_email"] == settings.admin_email
    assert data["analytics_id"] == settings.analytics_id


@pytest.mark.asyncio
async def test_site_config_url_has_no_trailing_slash(client: AsyncClient, monkeypatch):
    """A trailing slash in SITE_URL must not leak into canonical URLs."""
    monkeypatch.setattr(settings, "site_url", "https://example.test/")
    response = await client.get(f"{settings.api_prefix}/config/site")
    assert response.json()["site_url"] == "https://example.test"


@pytest.mark.asyncio
async def test_site_config_social_links_parsed_and_trimmed(
    client: AsyncClient, monkeypatch
):
    """Comma-separated links become a clean list; blanks are dropped."""
    monkeypatch.setattr(
        settings, "social_links", " https://a.example/x , ,https://b.example/y,"
    )
    response = await client.get(f"{settings.api_prefix}/config/site")
    assert response.json()["social_links"] == [
        "https://a.example/x",
        "https://b.example/y",
    ]


@pytest.mark.asyncio
async def test_site_config_empty_social_links(client: AsyncClient, monkeypatch):
    """No socials configured -> empty list, not an error."""
    monkeypatch.setattr(settings, "social_links", "")
    response = await client.get(f"{settings.api_prefix}/config/site")
    assert response.status_code == 200
    assert response.json()["social_links"] == []


@pytest.mark.asyncio
async def test_site_config_is_public(client: AsyncClient):
    """No auth required — the frontend fetches this before any login."""
    response = await client.get(
        f"{settings.api_prefix}/config/site", headers={"Authorization": ""}
    )
    assert response.status_code == 200
