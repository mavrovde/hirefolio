"""Transparent translation of recruiter messages (#248).

TRANSPARENT means three hard rules, all pinned by tests:
- the stored ORIGINAL is never mutated — translation lives in separate,
  re-runnable columns;
- the translation is clearly machine-labeled at the UI, with the original a
  toggle away;
- intake never fails or blocks because translation failed — it runs as a
  background task and records its own status.

The LLM boundary follows the stack's one fallback pattern (rule 10): Gemini
when a key is configured, local Ollama otherwise — private and free by
default, and CI's empty key can never reach a paid API.
"""

import json

import httpx

from app.config import settings
from app.database import async_session
from app.logger import logger
from app.models.interaction import Interaction
from app.services.ai import _generate_text_gemini

# One call does detection AND translation: two round-trips through a local
# LLM would double the latency for no accuracy gain at this task size.
_PROMPT = """You are a precise translation service. Analyze the MESSAGE below.

Reply with ONLY a JSON object, no prose, exactly this shape:
{{"language": "<ISO 639-1 code of the message's language>",
  "translation": "<the message translated to {target}, or an empty string if it is already {target}>"}}

MESSAGE:
{message}"""


def _parse(response_text: str) -> tuple[str, str] | None:
    """The model's JSON, defensively: a malformed reply is a failed
    translation, never an exception into the caller."""
    try:
        start = response_text.index("{")
        end = response_text.rindex("}") + 1
        data = json.loads(response_text[start:end])
        language = str(data.get("language") or "").strip().lower()[:8]
        translation = str(data.get("translation") or "").strip()
        if not language:
            return None
        return language, translation
    except (ValueError, TypeError):
        return None


async def _generate(prompt: str) -> str:
    """Gemini when configured, Ollama otherwise — the ai.py idiom."""
    gemini_response = await _generate_text_gemini(prompt)
    if gemini_response:
        logger.info("Using Gemini for translation")
        return gemini_response
    logger.info("Using Ollama for translation (fallback)")
    async with httpx.AsyncClient(
        timeout=settings.llm_request_timeout_seconds
    ) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.fast_generation_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
        )
        response.raise_for_status()
        return response.json().get("response", "")


async def translate_interaction(interaction_id) -> None:
    """Background target: detect + translate one interaction's message into
    the owner's language, writing ONLY the translated_* columns.

    Opens its OWN session — the request's session is gone by the time a
    background task runs, and sharing one would recreate exactly the
    lifecycle bugs the repo's conftest notes warn about.
    """
    if not settings.translation_enabled:
        return
    async with async_session() as db:
        interaction = await db.get(Interaction, interaction_id)
        if interaction is None:  # deleted before we ran — nothing to do
            return
        try:
            raw = await _generate(
                _PROMPT.format(
                    target=settings.owner_language, message=interaction.message
                )
            )
            parsed = _parse(raw)
            if parsed is None:
                interaction.translation_status = "failed"
            else:
                language, translation = parsed
                interaction.detected_language = language
                if language == settings.owner_language or not translation:
                    # Already the owner's language: detection alone is the
                    # useful output; there is nothing to translate.
                    interaction.translation_status = "not_needed"
                else:
                    interaction.translated_message = translation
                    interaction.translated_to = settings.owner_language
                    interaction.translation_status = "done"
        except Exception as e:
            # Never let a translation failure surface anywhere near intake.
            logger.error(f"Translation failed: {type(e).__name__}")
            interaction.translation_status = "failed"
        await db.commit()
