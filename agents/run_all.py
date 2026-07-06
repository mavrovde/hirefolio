"""Launch every agent in the roster locally (one uvicorn subprocess per role).

    python -m agents.run_all

Then, in another shell, drive the team:
    python -m agents.orchestrator "Add a LinkedIn post-sync feature"
"""
from __future__ import annotations

import signal
import subprocess
import sys

from agents.common.roster import ROSTER


def main() -> None:
    procs: list[subprocess.Popen] = []
    for key, spec in ROSTER.items():
        p = subprocess.Popen([sys.executable, "-m", "agents.serve", key])
        procs.append(p)
        print(f"[run_all] {spec.name} ({key}) -> http://localhost:{spec.port}"
              f"/.well-known/agent.json (pid {p.pid})", flush=True)

    def shutdown(*_):
        print("\n[run_all] stopping agents...", flush=True)
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    print(f"[run_all] {len(procs)} agents running. Ctrl-C to stop.", flush=True)
    for p in procs:
        p.wait()


if __name__ == "__main__":
    main()
