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
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"  # stronger reasoning/coding for autonomous work


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


async def think_with_tools(system_prompt: str, user_text: str, *, role_title: str = "agent",
                           model: str | None = None, max_iters: int = 10,
                           allowed_tools: set[str] | None = None) -> str:
    """Like think(), but the model can call repo tools (scoped to allowed_tools)
    in a ReAct loop. Ollama-backed (function-calling); falls back to plain think()
    for non-Ollama providers or if the tool loop errors."""
    from .tools import READONLY_TOOLS

    allowed = allowed_tools if allowed_tools is not None else set(READONLY_TOOLS)
    for prov in _order():
        try:
            if prov == "ollama":
                return await _ollama_tools(system_prompt, user_text, model, max_iters, allowed)
            if prov == "gemini" and os.getenv("GEMINI_API_KEY"):
                return await _gemini_tools(system_prompt, user_text, model, max_iters, allowed)
        except Exception:  # noqa: BLE001 - try the next provider / fall back
            continue
    return await think(system_prompt, user_text, role_title=role_title, model=model)


async def _gemini_tools(system_prompt: str, user_text: str, model: str | None,
                        max_iters: int, allowed: set[str]) -> str:
    from google import genai
    from google.genai import types

    from .tools import execute_tool, schemas_for

    fdecls = [types.FunctionDeclaration(
        name=s["function"]["name"], description=s["function"]["description"],
        parameters=s["function"]["parameters"]) for s in schemas_for(allowed)]
    config = types.GenerateContentConfig(
        system_instruction=system_prompt, temperature=0.2,
        tools=[types.Tool(function_declarations=fdecls)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    mdl = model or os.getenv("A2A_MODEL") or DEFAULT_GEMINI_MODEL
    contents = [types.Content(role="user", parts=[types.Part(text=user_text)])]
    for _ in range(max_iters):
        resp = await client.aio.models.generate_content(model=mdl, contents=contents, config=config)
        cand = resp.candidates[0]
        parts = cand.content.parts or []
        calls = [p.function_call for p in parts if getattr(p, "function_call", None)]
        if not calls:
            return (resp.text or "").strip()
        contents.append(cand.content)
        fr = []
        for fc in calls:
            result = execute_tool(fc.name, dict(fc.args) if fc.args else {}, allowed)
            fr.append(types.Part(function_response=types.FunctionResponse(
                name=fc.name, response={"result": str(result)[:8000]})))
        contents.append(types.Content(role="user", parts=fr))
    # Out of iterations — ask for a final answer without tools.
    resp = await client.aio.models.generate_content(
        model=mdl,
        contents=contents + [types.Content(role="user",
                 parts=[types.Part(text="Stop using tools. Give your final answer now.")])],
        config=types.GenerateContentConfig(system_instruction=system_prompt))
    return (resp.text or "").strip()


async def _ollama_tools(system_prompt: str, user_text: str, model: str | None,
                        max_iters: int, allowed: set[str]) -> str:
    from .tools import execute_tool, schemas_for

    schemas = schemas_for(allowed)
    mdl = model or os.getenv("A2A_MODEL") or DEFAULT_OLLAMA_MODEL
    messages = [
        {"role": "system", "content": system_prompt
         + "\n\nYou have tools to inspect and modify the repository and run tests. "
           "Use them to ground every claim in reality; never guess file contents or "
           "test results — read/run them. When done, give a concise final answer."},
        {"role": "user", "content": user_text},
    ]
    async with httpx.AsyncClient(timeout=600) as client:
        for _ in range(max_iters):
            r = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": mdl, "messages": messages, "tools": schemas,
                      "stream": False, "options": {"temperature": 0.2}},
            )
            r.raise_for_status()
            msg = r.json()["message"]
            calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            if not calls:
                # Some models (e.g. qwen via Ollama) emit tool calls as JSON in
                # content instead of the structured tool_calls field — parse those.
                calls = _parse_tool_calls_from_content(content)
            if not calls:
                return content.strip()
            messages.append(msg)
            for tc in calls:
                fn = tc.get("function", {})
                result = execute_tool(fn.get("name", ""), fn.get("arguments", {}) or {}, allowed)
                messages.append({"role": "tool", "content": str(result)[:8000]})
        # Out of iterations — ask for a final answer without tools.
        r = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": mdl,
                  "messages": messages + [{"role": "user", "content":
                      "Stop using tools. Give your final answer now."}],
                  "stream": False, "options": {"temperature": 0.2}},
        )
        r.raise_for_status()
        return (r.json()["message"].get("content") or "").strip()


def _parse_tool_calls_from_content(content: str) -> list[dict]:
    """Extract tool calls a model emitted as JSON in its message content.
    Only returns calls whose name is a real registered tool (so a plain JSON
    final answer isn't mistaken for a tool call)."""
    import json
    import re

    from .tools import REGISTRY

    if not content or "{" not in content:
        return []
    text = content.strip()
    for token in ("```json", "```", "<tool_call>", "</tool_call>"):
        text = text.replace(token, "")
    text = text.strip()
    obj = None
    try:
        obj = json.loads(text)
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
            except Exception:  # noqa: BLE001
                return []
    if obj is None:
        return []
    items = obj if isinstance(obj, list) else [obj]
    calls = []
    for it in items:
        if isinstance(it, dict) and it.get("name") in REGISTRY:
            calls.append({"function": {
                "name": it["name"],
                "arguments": it.get("arguments") or it.get("parameters") or {},
            }})
    return calls


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
