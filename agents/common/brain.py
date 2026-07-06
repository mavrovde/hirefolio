"""The reasoning 'brain' shared by every agent.

If ANTHROPIC_API_KEY is set (and the `anthropic` package is installed) each agent
thinks with Claude. Otherwise it falls back to a deterministic stub so the whole
A2A team is runnable and testable offline / in CI without any API key.
"""
from __future__ import annotations

import os

DEFAULT_MODEL = os.getenv("A2A_MODEL", "claude-opus-4-8")


def llm_enabled() -> bool:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


async def think(system_prompt: str, user_text: str, *, role_title: str = "agent",
                model: str | None = None) -> str:
    """Produce this agent's response to an incoming A2A message."""
    if not llm_enabled():
        return _stub(role_title, system_prompt, user_text)

    import anthropic

    client = anthropic.AsyncAnthropic()
    resp = await client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


def _stub(role_title: str, system_prompt: str, user_text: str) -> str:
    """Deterministic, offline response — structured so pipelines and tests work
    without an API key. Clearly labeled so it's never mistaken for real output."""
    focus = system_prompt.strip().split(".")[0]
    return (
        f"[stub:{role_title}] (no ANTHROPIC_API_KEY — deterministic response)\n"
        f"Role focus: {focus}.\n"
        f"Task received: {user_text.strip()[:500]}\n"
        f"Proposed next step: a real Claude-backed run would produce the "
        f"{role_title} deliverable for this task."
    )
