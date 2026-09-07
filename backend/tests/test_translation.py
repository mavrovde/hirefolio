"""Transparent translation (#248), pinned criterion by criterion.

The LLM boundary is mocked everywhere (rule 10): `_generate` at the service
seam for behavior tests, plus one Gemini-vs-Ollama routing test at the real
fallback fork with both transports mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.interaction import Interaction
from app.services.translation import _parse, translate_interaction

CONTACT = f"{settings.api_prefix}/interactions/contact"
ADMIN = f"{settings.api_prefix}/admin/interactions"

GERMAN_JSON = '{"language": "de", "translation": "Hello, are you open to a new role?"}'


async def _row(client: AsyncClient, interaction_id: str) -> dict:
    """No GET-by-id exists on the admin router; the list is the read path."""
    page = (await client.get(f"{ADMIN}?page_size=50")).json()
    return next(i for i in page["items"] if i["id"] == interaction_id)


async def _submit(client: AsyncClient, message: str = "Hallo, sind Sie offen?"):
    r = await client.post(
        CONTACT,
        json={"name": "Rita", "email": "rita@agency.example", "message": message},
    )
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------- criterion 1


@pytest.mark.asyncio
async def test_german_message_gets_language_badge_and_labeled_translation(
    client: AsyncClient,
):
    """Original intact, detected language recorded, translation in SEPARATE
    fields — the transparency contract."""
    with patch(
        "app.services.translation._generate",
        new=AsyncMock(return_value=GERMAN_JSON),
    ):
        created = await _submit(client)

    row = await _row(client, created["id"])
    assert row["message"] == "Hallo, sind Sie offen?"  # NEVER mutated
    assert row["detected_language"] == "de"
    assert row["translated_message"] == "Hello, are you open to a new role?"
    assert row["translated_to"] == "en"
    assert row["translation_status"] == "done"


@pytest.mark.asyncio
async def test_owner_language_message_needs_no_translation(client: AsyncClient):
    with patch(
        "app.services.translation._generate",
        new=AsyncMock(return_value='{"language": "en", "translation": ""}'),
    ):
        created = await _submit(client, message="Hello, are you available?")
    row = await _row(client, created["id"])
    assert row["detected_language"] == "en"
    assert row["translated_message"] is None
    assert row["translation_status"] == "not_needed"


# ---------------------------------------------------------------- criterion 2


@pytest.mark.asyncio
async def test_translation_failure_never_touches_intake(client: AsyncClient):
    """The LLM exploding leaves a 201, a stored original, and status=failed."""
    with patch(
        "app.services.translation._generate",
        new=AsyncMock(side_effect=RuntimeError("model on fire")),
    ):
        created = await _submit(client)
    row = await _row(client, created["id"])
    assert row["message"] == "Hallo, sind Sie offen?"
    assert row["translation_status"] == "failed"
    assert row["translated_message"] is None


@pytest.mark.asyncio
async def test_garbage_model_output_is_a_failure_not_an_exception(
    client: AsyncClient,
):
    with patch(
        "app.services.translation._generate",
        new=AsyncMock(return_value="I'm sorry, as an AI model I cannot"),
    ):
        created = await _submit(client)
    row = await _row(client, created["id"])
    assert row["translation_status"] == "failed"


# ---------------------------------------------------------------- criterion 3


@pytest.mark.asyncio
async def test_empty_gemini_key_routes_to_ollama_and_key_routes_to_gemini():
    """The stack's ONE fallback pattern, at the real fork — both transports
    mocked (rule 10: no test reaches a paid API or a real Ollama)."""
    from app.services import translation as t

    # Empty key: _generate_text_gemini yields falsy -> Ollama POST happens.
    ollama = MagicMock()
    ollama.raise_for_status = lambda: None
    ollama.json = lambda: {"response": GERMAN_JSON}
    with (
        patch(
            "app.services.translation._generate_text_gemini",
            new=AsyncMock(return_value=None),
        ),
        patch("app.services.translation.httpx.AsyncClient") as client_cls,
    ):
        client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=ollama
        )
        assert await t._generate("p") == GERMAN_JSON
        posted = client_cls.return_value.__aenter__.return_value.post.call_args
        assert posted.args[0].endswith("/api/generate")

    # Key present: Gemini answers; Ollama must never be contacted.
    with (
        patch(
            "app.services.translation._generate_text_gemini",
            new=AsyncMock(return_value=GERMAN_JSON),
        ),
        patch("app.services.translation.httpx.AsyncClient") as client_cls,
    ):
        assert await t._generate("p") == GERMAN_JSON
        client_cls.assert_not_called()


# ---------------------------------------------------------------- criterion 4


@pytest.mark.asyncio
async def test_rerun_overwrites_only_translated_fields(client: AsyncClient):
    with patch(
        "app.services.translation._generate",
        new=AsyncMock(return_value=GERMAN_JSON),
    ):
        created = await _submit(client)

    better = '{"language": "de", "translation": "Hello — open to a new position?"}'
    with patch(
        "app.services.translation._generate", new=AsyncMock(return_value=better)
    ):
        r = await client.post(f"{ADMIN}/{created['id']}/translate")
        assert r.status_code == 200

    row = await _row(client, created["id"])
    assert row["message"] == "Hallo, sind Sie offen?"  # STILL untouched
    assert row["translated_message"] == "Hello — open to a new position?"
    assert row["translation_status"] == "done"


@pytest.mark.asyncio
async def test_rerun_unknown_interaction_is_404(client: AsyncClient):
    r = await client.post(f"{ADMIN}/00000000-0000-0000-0000-000000000000/translate")
    assert r.status_code == 404


# ---------------------------------------------------------------- criterion 5


@pytest.mark.asyncio
async def test_flag_off_schedules_nothing_and_rerun_409s(client: AsyncClient):
    """Disabled means DISABLED: no background task, no LLM call, no fields
    set — and the re-run endpoint refuses rather than pretending."""
    with (
        patch("app.config.settings.translation_enabled", False),
        patch("app.services.translation._generate", new=AsyncMock()) as gen,
    ):
        created = await _submit(client)
        gen.assert_not_called()
        row = await _row(client, created["id"])
        assert row["translation_status"] is None
        assert (
            await client.post(f"{ADMIN}/{created['id']}/translate")
        ).status_code == 409


@pytest.mark.asyncio
async def test_flag_off_inside_the_task_is_also_inert(db_session):
    """Belt AND braces: even a task already scheduled before the flag flipped
    writes nothing."""
    row = Interaction(
        source="contact_form",
        name="R",
        email="r@example.com",
        message="Hallo",
    )
    db_session.add(row)
    await db_session.commit()
    with (
        patch("app.config.settings.translation_enabled", False),
        patch("app.services.translation._generate", new=AsyncMock()) as gen,
    ):
        await translate_interaction(row.id)
        gen.assert_not_called()


# ------------------------------------------------------------------- parsing


def test_parse_extracts_json_from_chatty_output():
    assert _parse('Sure! {"language": "fr", "translation": "Hi"} hope that helps') == (
        "fr",
        "Hi",
    )
    assert _parse('{"language": "", "translation": "x"}') is None
    assert _parse("not json at all") is None


@pytest.mark.asyncio
async def test_deleted_interaction_is_a_noop(client: AsyncClient):
    await translate_interaction("00000000-0000-0000-0000-000000000000")
