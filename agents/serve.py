"""Run one A2A agent.

Usage:
    A2A_ROLE=architect python -m agents.serve
    python -m agents.serve architect
"""
from __future__ import annotations

import os
import sys

import uvicorn

from agents.common.roster import ROSTER
from agents.common.server import build_app_for


def main() -> None:
    role = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("A2A_ROLE", "")).strip()
    if not role:
        raise SystemExit(f"Specify a role. Known: {', '.join(ROSTER)}")
    spec = ROSTER[role]
    app = build_app_for(role)
    host = os.getenv("A2A_BIND", "0.0.0.0")
    port = int(os.getenv("A2A_PORT", spec.port))
    print(f"[a2a] serving '{spec.name}' ({role}) on http://{host}:{port}  "
          f"card: http://{host}:{port}/.well-known/agent.json")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
