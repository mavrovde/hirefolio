"""Run one A2A agent.

Usage:
    A2A_ROLE=architect python -m agents.serve
    python -m agents.serve architect
"""
from __future__ import annotations

import os
import socket
import sys
import time

import uvicorn

from agents.common.roster import ROSTER
from agents.common.server import build_app_for


def _wait_port_free(host: str, port: int, attempts: int = 24, delay: float = 0.5) -> bool:
    """Wait until `port` is bindable. A just-killed sibling agent (e.g. the
    release-manager on :8021) can still hold its socket when the next run starts,
    which used to crash the bind with 'address already in use'. Poll until it frees
    (up to ~12s) so restarts are reliable."""
    bind_host = "" if host in ("0.0.0.0", "::", "") else host
    for i in range(attempts):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((bind_host, port))
            s.close()
            return True
        except OSError:
            s.close()
            if i == 0:
                print(f"[a2a] port {port} busy — waiting for it to free…", flush=True)
            time.sleep(delay)
    return False


def main() -> None:
    role = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("A2A_ROLE", "")).strip()
    if not role:
        raise SystemExit(f"Specify a role. Known: {', '.join(ROSTER)}")
    spec = ROSTER[role]
    app = build_app_for(role)
    host = os.getenv("A2A_BIND", "0.0.0.0")
    port = int(os.getenv("A2A_PORT", spec.port))
    _wait_port_free(host, port)
    print(f"[a2a] serving '{spec.name}' ({role}) on http://{host}:{port}  "
          f"card: http://{host}:{port}/.well-known/agent.json")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
