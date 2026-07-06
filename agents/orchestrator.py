"""Project-Manager orchestrator — a real A2A *client*.

Given a goal, it discovers each specialist via its Agent Card and delegates work
over the A2A wire protocol (JSON-RPC message/send), chaining the artifacts into a
delivery transcript, then synthesizes a PM summary.

Usage:
    python -m agents.orchestrator "Add a LinkedIn post-sync feature to the blog"
    python -m agents.orchestrator "<goal>" --roles architect,backend-dev,qa-engineer
"""
from __future__ import annotations

import argparse
import asyncio
import uuid

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart

from agents.common.brain import think
from agents.common.roster import (
    DELIVERY_PIPELINE, DEPENDENCIES, PROJECT_MANAGER, ROSTER, RoleSpec,
)


def _artifact_text(resp) -> str:
    data = resp.model_dump(mode="json", exclude_none=True)
    result = data.get("result", {})
    for art in result.get("artifacts", []) or []:
        for part in art.get("parts", []) or []:
            if "text" in part:
                return part["text"]
    # fall back to a status message if no artifact
    status = (result.get("status") or {}).get("message") or {}
    for part in status.get("parts", []) or []:
        if "text" in part:
            return part["text"]
    return "(no textual artifact returned)"


async def _resolve_card(hx: httpx.AsyncClient, spec: RoleSpec, attempts: int = 20):
    """Resolve an Agent Card, retrying with capped backoff so a slow-to-start
    agent (e.g. one of many booting at once) is not missed (~30s total)."""
    resolver = A2ACardResolver(httpx_client=hx, base_url=spec.host())
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await resolver.get_agent_card()
        except Exception as exc:  # noqa: BLE001 - transient startup/network errors
            last = exc
            await asyncio.sleep(min(2.0, 0.5 * (i + 1)))
    raise last  # type: ignore[misc]


async def delegate(hx: httpx.AsyncClient, spec: RoleSpec, prompt: str) -> str:
    """Discover an agent by its Agent Card and send it one A2A task."""
    card = await _resolve_card(hx, spec)
    client = A2AClient(httpx_client=hx, agent_card=card)
    req = SendMessageRequest(
        id=str(uuid.uuid4()),
        params=MessageSendParams(
            message=Message(
                role=Role.user,
                message_id=uuid.uuid4().hex,
                parts=[Part(root=TextPart(text=prompt))],
            )
        ),
    )
    resp = await client.send_message(req)
    return _artifact_text(resp)


def _build_context(role_key: str, goal: str, plan: str, results: dict[str, str]) -> str:
    """Give a role focused input: the PM plan + the outputs of the roles it
    explicitly depends on (falling back to nothing extra if it's a starter)."""
    deps = DEPENDENCIES.get(role_key, [])
    parts = [f"Delivery goal:\n{goal}", f"Project Manager plan:\n{plan}"]
    for dep in deps:
        if dep in results:
            parts.append(f"Input from {ROSTER[dep].name} ({dep}):\n{results[dep]}")
    spec = ROSTER[role_key]
    parts.append(f"Now perform your role as {spec.name} ({spec.title}). "
                 f"Use the inputs above; produce your deliverable.")
    return "\n\n".join(parts)


async def orchestrate(goal: str, roles: list[str] | None = None) -> dict:
    pipeline = roles or DELIVERY_PIPELINE
    transcript: list[tuple[str, str]] = []
    results: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=120) as hx:
        # PM plans first (its own brain).
        plan = await think(PROJECT_MANAGER.system_prompt,
                           f"Goal: {goal}\nTeam: {', '.join(pipeline)}",
                           role_title=PROJECT_MANAGER.title)
        transcript.append(("project-manager (plan)", plan))
        print(f"\n=== Project Manager plan ===\n{plan}\n")

        # Delegate down the pipeline, giving each agent focused dependency context.
        for role_key in pipeline:
            spec = ROSTER[role_key]
            prompt = _build_context(role_key, goal, plan, results)
            deps = [d for d in DEPENDENCIES.get(role_key, []) if d in results]
            print(f"--> delegating to {spec.name} ({role_key}) at {spec.host()}"
                  f"{'  <- inputs: ' + ', '.join(deps) if deps else ''}")
            try:
                out = await delegate(hx, spec, prompt)
            except Exception as exc:
                out = f"(unreachable: {exc})"
            results[role_key] = out
            transcript.append((role_key, out))
            print(f"<-- {spec.name}: {out.splitlines()[0][:100] if out else ''}")

        # PM synthesizes the final report.
        summary_input = "\n\n".join(f"## {who}\n{txt}" for who, txt in transcript)
        report = await think(
            PROJECT_MANAGER.system_prompt,
            f"Goal: {goal}\n\nTeam transcript:\n{summary_input}\n\n"
            f"Write the final delivery summary: what was produced, status, and open risks.",
            role_title="Delivery summary",
        )
    print(f"\n=== Final delivery report ===\n{report}\n")
    return {"goal": goal, "transcript": transcript, "report": report}


def main() -> None:
    ap = argparse.ArgumentParser(description="A2A Project-Manager orchestrator")
    ap.add_argument("goal", help="the delivery goal to orchestrate")
    ap.add_argument("--roles", help="comma-separated role keys (default: full pipeline)")
    args = ap.parse_args()
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
    asyncio.run(orchestrate(args.goal, roles))


if __name__ == "__main__":
    main()
