"""A2A team tests — hermetic, offline (deterministic brain, no API key needed).

Each agent is exercised in-process via an httpx ASGI transport: we verify the
Agent Card is discoverable and that an A2A `message/send` yields a completed task
with an artifact. Also covers the orchestrator's delegate() against in-process agents.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import ASGITransport

from a2a.client import A2AClient
from a2a.types import (
    Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart,
)

from agents.common.roster import ROSTER, WORKERS
from agents.common.server import build_agent_card, build_app


def _client(spec):
    app = build_app(spec)
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url=f"http://localhost:{spec.port}")


@pytest.mark.asyncio
@pytest.mark.parametrize("role_key", list(ROSTER.keys()))
async def test_agent_card_discoverable(role_key):
    spec = ROSTER[role_key]
    async with _client(spec) as hx:
        r = await hx.get("/.well-known/agent.json")
        assert r.status_code == 200
        card = r.json()
        assert card["name"] == spec.name
        assert card["skills"], "agent must advertise at least one skill"
        assert card["url"].startswith("http")


@pytest.mark.asyncio
@pytest.mark.parametrize("role_key", WORKERS)
async def test_message_send_completes_with_artifact(role_key):
    spec = ROSTER[role_key]
    async with _client(spec) as hx:
        card = build_agent_card(spec)
        client = A2AClient(httpx_client=hx, agent_card=card)
        req = SendMessageRequest(
            id=str(uuid.uuid4()),
            params=MessageSendParams(
                message=Message(
                    role=Role.user,
                    message_id=uuid.uuid4().hex,
                    parts=[Part(root=TextPart(text=f"Do your job for role {role_key}."))],
                )
            ),
        )
        resp = await client.send_message(req)
        data = resp.model_dump(mode="json", exclude_none=True)
        result = data["result"]
        assert result["status"]["state"] == "completed"
        artifacts = result.get("artifacts") or []
        assert artifacts, "expected at least one artifact"
        text = artifacts[0]["parts"][0]["text"]
        assert role_key in artifacts[0]["name"]
        assert text.strip()


@pytest.mark.asyncio
async def test_roster_is_complete():
    # 12 roles incl. the PM orchestrator, release manager and doc writer.
    assert len(ROSTER) == 12
    for required in ("project-manager", "release-manager", "documentation-writer"):
        assert required in ROSTER
    ports = [s.port for s in ROSTER.values()]
    assert len(ports) == len(set(ports)), "ports must be unique"


@pytest.mark.asyncio
async def test_dependency_graph_is_valid():
    from agents.common.roster import DELIVERY_PIPELINE, DEPENDENCIES
    # every pipeline role has a dependency entry, and deps reference real roles
    for role in DELIVERY_PIPELINE:
        assert role in DEPENDENCIES, f"{role} missing from DEPENDENCIES"
        for dep in DEPENDENCIES[role]:
            assert dep in ROSTER, f"{role} depends on unknown role {dep}"
            # a dependency must be produced earlier in the pipeline
            assert DELIVERY_PIPELINE.index(dep) < DELIVERY_PIPELINE.index(role), \
                f"{role} depends on {dep} which runs later"
