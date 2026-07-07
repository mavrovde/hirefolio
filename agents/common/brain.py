"""The reasoning 'brain' shared by every agent — provider-pluggable.

Provider is chosen by A2A_LLM_PROVIDER: ollama | anthropic | gemini | stub | auto
(default 'anthropic': the team runs on Claude, with prompt caching on the system
prompt + tool definitions). Set A2A_LLM_PROVIDER=auto for the no-cost path (local
Ollama, then a deterministic offline stub) or =ollama/=gemini/=stub explicitly.
Anthropic needs ANTHROPIC_API_KEY; without it the anthropic path degrades to the
labelled stub (never a silent charge).

Models per provider come from A2A_MODEL, with sensible defaults:
  - anthropic -> claude-sonnet-4-6  (strong+cost-effective; claude-opus-4-8 for max)
  - ollama    -> qwen2.5-coder:7b   (great code+reasoning on Apple-silicon/16GB)
Ollama endpoint via OLLAMA_URL (default http://localhost:11434).
"""
from __future__ import annotations

import os

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"  # strong+cost-effective; opus-4-8 for max
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"  # stronger reasoning/coding for autonomous work


def _log_usage(resp, where: str) -> None:
    """Observability for prompt caching: with A2A_LOG_USAGE=1, print token usage
    incl. cache read/write so you can *verify* the cache is being hit (cache_read>0
    after the first call of a role within the ~5 min TTL). No-op otherwise."""
    if os.getenv("A2A_LOG_USAGE") != "1":
        return
    u = getattr(resp, "usage", None)
    if u is None:
        return
    print(
        f"[brain:{where}] in={getattr(u, 'input_tokens', 0)} "
        f"out={getattr(u, 'output_tokens', 0)} "
        f"cache_write={getattr(u, 'cache_creation_input_tokens', 0)} "
        f"cache_read={getattr(u, 'cache_read_input_tokens', 0)}",
        flush=True,
    )


def _order() -> list[str]:
    provider = os.getenv("A2A_LLM_PROVIDER", "anthropic").lower()
    return {
        "ollama": ["ollama"],
        "anthropic": ["anthropic"],
        "gemini": ["gemini"],
        "stub": ["stub"],
        # 'auto' never falls back to a PAID provider — only free local Ollama, then
        # the offline stub. Paid providers (anthropic/gemini) must be requested
        # explicitly via A2A_LLM_PROVIDER, so a run can't silently cost money.
        "auto": ["ollama", "stub"],
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
            if prov == "anthropic" and _anthropic_ready():
                return await _anthropic_tools(system_prompt, user_text, model, max_iters, allowed)
        except Exception:  # noqa: BLE001 - try the next provider / fall back
            continue
    return await think(system_prompt, user_text, role_title=role_title, model=model)


async def _anthropic_tools(system_prompt: str, user_text: str, model: str | None,
                           max_iters: int, allowed: set[str]) -> str:
    from anthropic import AsyncAnthropic

    from .tools import execute_tool, schemas_for

    tools = [{"name": s["function"]["name"], "description": s["function"]["description"],
              "input_schema": s["function"]["parameters"]} for s in schemas_for(allowed)]
    # Prompt caching: the system prompt (playbook + role) and tool defs are identical
    # across every call, so mark them cacheable (ephemeral, ~5 min TTL) to cut cost/latency.
    if tools:
        tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
    sys_cached = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    client = AsyncAnthropic()
    mdl = model or os.getenv("A2A_MODEL") or DEFAULT_ANTHROPIC_MODEL
    messages: list = [{"role": "user", "content": user_text}]
    prev_cached: dict | None = None  # rolling breakpoint on the tool transcript
    for _ in range(max_iters):
        resp = await client.messages.create(model=mdl, max_tokens=4096, temperature=0,
                                            system=sys_cached, tools=tools, messages=messages)
        _log_usage(resp, "anthropic_tools")
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                out = execute_tool(b.name, b.input or {}, allowed)
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": str(out)[:8000]})
        # Cache the transcript up to *this* turn's tool results so the next turn reads
        # the whole prior conversation from cache. Keep exactly one message-level
        # breakpoint (system + last tool def use the other two) — move it each turn.
        if prev_cached is not None:
            prev_cached.pop("cache_control", None)
        if results:
            results[-1]["cache_control"] = {"type": "ephemeral"}
            prev_cached = results[-1]
        messages.append({"role": "user", "content": results})
    resp = await client.messages.create(
        model=mdl, max_tokens=2048, temperature=0, system=sys_cached, tools=tools,
        messages=messages + [{"role": "user", "content": "Stop using tools. Final answer now."}])
    _log_usage(resp, "anthropic_tools")
    return "".join(b.text for b in resp.content if b.type == "text").strip()


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
        max_tokens=1024, temperature=0,
        # cache the system prompt (reused across calls) — ephemeral ~5 min TTL
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_text}],
    )
    _log_usage(resp, "anthropic")
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
