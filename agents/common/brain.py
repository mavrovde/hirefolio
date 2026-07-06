"""The reasoning 'brain' shared by every agent — provider-pluggable.

Provider is chosen by A2A_LLM_PROVIDER: ollama | anthropic | gemini | stub | auto
(default 'auto': try Ollama, then Anthropic if a key is set, else a deterministic
stub so the team is always runnable/testable offline).

Models per provider come from A2A_MODEL, with sensible defaults:
  - ollama    -> qwen2.5-coder:7b   (great code+reasoning on Apple-silicon/16GB)
  - anthropic -> claude-opus-4-8
Ollama endpoint via OLLAMA_URL (default http://localhost:11434).
"""
from __future__ import annotations

import os

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"


def _order() -> list[str]:
    provider = os.getenv("A2A_LLM_PROVIDER", "auto").lower()
    return {
        "ollama": ["ollama"],
        "anthropic": ["anthropic"],
        "gemini": ["gemini"],
        "stub": ["stub"],
        "auto": ["ollama", "anthropic", "stub"],
    }.get(provider, ["stub"])


async def think(system_prompt: str, user_text: str, *, role_title: str = "agent",
                model: str | None = None) -> str:
    """Produce this agent's response to an incoming A2A message, using the first
    provider in the resolved order that is available/succeeds."""
    last_err: Exception | None = None
    for prov in _order():
        try:
            if prov == "ollama":
                return await _ollama(system_prompt, user_text, model)
            if prov == "anthropic":
                if not _anthropic_ready():
                    continue
                return await _anthropic(system_prompt, user_text, model)
            if prov == "gemini":
                if not os.getenv("GEMINI_API_KEY"):
                    continue
                return await _gemini(system_prompt, user_text, model)
            if prov == "stub":
                return _stub(role_title, system_prompt, user_text)
        except Exception as exc:  # noqa: BLE001 - fall through to the next provider
            last_err = exc
            continue
    return _stub(role_title, system_prompt, user_text, error=last_err)


async def _ollama(system_prompt: str, user_text: str, model: str | None) -> str:
    mdl = model or os.getenv("A2A_MODEL") or DEFAULT_OLLAMA_MODEL
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": mdl,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                "stream": False,
                "options": {"temperature": 0.3},
            },
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()


def _anthropic_ready() -> bool:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


async def _anthropic(system_prompt: str, user_text: str, model: str | None) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic()
    resp = await client.messages.create(
        model=model or os.getenv("A2A_MODEL") or DEFAULT_ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


async def _gemini(system_prompt: str, user_text: str, model: str | None) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = await client.aio.models.generate_content(
        model=model or os.getenv("A2A_MODEL") or "gemini-2.0-flash",
        contents=user_text,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    return (resp.text or "").strip()


def _stub(role_title: str, system_prompt: str, user_text: str, error: Exception | None = None) -> str:
    """Deterministic offline fallback — clearly labelled so it's never mistaken
    for real output. Used when no provider is reachable (e.g. no Ollama, no key)."""
    focus = system_prompt.strip().split(".")[0]
    why = f" (providers unavailable: {error})" if error else " (no LLM provider configured)"
    return (
        f"[stub:{role_title}]{why}\n"
        f"Role focus: {focus}.\n"
        f"Task received: {user_text.strip()[:500]}\n"
        f"Set A2A_LLM_PROVIDER=ollama (with Ollama running) for real output."
    )
