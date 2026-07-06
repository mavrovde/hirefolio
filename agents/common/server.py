"""Build the A2A server (Agent Card + JSON-RPC app) for a given role."""
from __future__ import annotations

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentProvider, AgentSkill

from .executor import RoleExecutor
from .roster import ROSTER, RoleSpec


def build_agent_card(spec: RoleSpec) -> AgentCard:
    return AgentCard(
        name=spec.name,
        description=spec.description,
        url=f"{spec.host().rstrip('/')}/",
        version="1.0.0",
        provider=AgentProvider(organization="mavrov.de", url="https://mavrov.de"),
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text", "text/plain"],
        default_output_modes=["text", "text/plain"],
        skills=[
            AgentSkill(
                id=s.id, name=s.name, description=s.description,
                tags=s.tags, examples=s.examples or None,
            )
            for s in spec.skills
        ],
    )


def build_app(spec: RoleSpec):
    """Return the ASGI app for one A2A agent (serves the Agent Card at
    /.well-known/agent.json and the JSON-RPC endpoint)."""
    card = build_agent_card(spec)
    handler = DefaultRequestHandler(
        agent_executor=RoleExecutor(spec),
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(agent_card=card, http_handler=handler).build()


def build_app_for(role_key: str):
    if role_key not in ROSTER:
        raise SystemExit(f"Unknown role '{role_key}'. Known: {', '.join(ROSTER)}")
    return build_app(ROSTER[role_key])
