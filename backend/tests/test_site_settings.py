"""Availability setting (#271): admin-editable at runtime, public on /config/site."""

import pytest
from httpx import AsyncClient

from app.config import settings

PUBLIC = f"{settings.api_prefix}/config/site"
ADMIN = f"{settings.api_prefix}/admin/site-settings/availability"


@pytest.mark.asyncio
async def test_public_config_defaults_to_listening(client: AsyncClient):
    r = await client.get(PUBLIC)
    assert r.status_code == 200
    assert r.json()["availability"] == "listening"


@pytest.mark.asyncio
async def test_admin_sets_availability_and_public_config_reflects_it(
    client: AsyncClient,
):
    assert (await client.put(ADMIN, json={"value": "open"})).json() == {"value": "open"}
    assert (await client.get(PUBLIC)).json()["availability"] == "open"

    # Update path (row exists now), not just insert.
    assert (await client.put(ADMIN, json={"value": "not_looking"})).status_code == 200
    assert (await client.get(PUBLIC)).json()["availability"] == "not_looking"
    assert (await client.get(ADMIN)).json() == {"value": "not_looking"}


@pytest.mark.asyncio
async def test_unknown_state_is_422_and_changes_nothing(client: AsyncClient):
    r = await client.put(ADMIN, json={"value": "yolo"})
    assert r.status_code == 422
    assert "must be one of" in r.json()["detail"]
    assert (await client.get(PUBLIC)).json()["availability"] == "listening"


@pytest.mark.asyncio
async def test_write_requires_admin_auth(normal_client: AsyncClient):
    """The read side is public BY WAY OF /config/site; the write side is not.
    normal_client carries a non-admin user, which must be rejected."""
    r = await normal_client.put(ADMIN, json={"value": "open"})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_states_vocabulary_matches_the_frontend_translations(
    client: AsyncClient,
):
    """A new state without translations renders as a raw key on the public
    hero. This test fails BEFORE that ships: every allowed state must have an
    AVAILABILITY.<STATE> entry in both language files."""
    import json
    from pathlib import Path

    from app.api.site_settings import AVAILABILITY_STATES

    i18n = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "projects"
        / "shared"
        / "assets"
        / "i18n"
    )
    for lang in ("en", "de"):
        table = json.loads((i18n / f"{lang}.json").read_text())
        for state in AVAILABILITY_STATES:
            key = state.upper()
            assert key in table.get("AVAILABILITY", {}), (
                f"{lang}.json is missing AVAILABILITY.{key}"
            )
