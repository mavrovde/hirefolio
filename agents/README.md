# mavrov.de — A2A Agent Team

A team of role-based AI agents that interoperate over the **A2A (Agent2Agent) protocol**.
Each role is an independent **A2A server** exposing an **Agent Card** at
`/.well-known/agent.json` and a JSON-RPC endpoint (`message/send`, `tasks/*`,
SSE streaming). The **Project Manager** is also an **A2A client** that discovers
the specialists via their Agent Cards and delegates work over the wire.

Built on the canonical [`a2a-sdk`](https://pypi.org/project/a2a-sdk/) (0.2.x).

## Roster (12 agents)

| Role | Key | Port | Purpose |
|------|-----|------|---------|
| Project Manager | `project-manager` | 8010 | Plans & orchestrates the team (A2A client) |
| Solution Architect | `architect` | 8011 | Technical design, interfaces, trade-offs |
| Story Writer | `story-writer` | 8012 | User stories + acceptance criteria |
| Backend Developer | `backend-dev` | 8013 | FastAPI / Python implementation |
| Frontend Developer | `frontend-dev` | 8014 | Angular 21 / TS implementation |
| QA Engineer | `qa-engineer` | 8015 | Test plans, verification, coverage |
| Code Reviewer | `code-reviewer` | 8016 | Correctness / security / quality review |
| LinkedIn Checker | `linkedin-checker` | 8017 | Validates the LinkedIn integration |
| DevOps | `devops` | 8018 | CI/CD pipeline diagnosis & fixes |
| Security Reviewer | `security-reviewer` | 8019 | Dependabot / CodeQL triage, AppSec |
| Documentation Writer | `documentation-writer` | 8020 | Docs, READMEs, CHANGELOG |
| Release Manager | `release-manager` | 8021 | SemVer bump, release notes, Go/No-Go |

## Delivery flow

The PM runs specialists in SDLC order, and each agent receives **focused context
from the roles it depends on** (not just the previous message):

```
architect → story-writer → backend-dev → frontend-dev → qa-engineer
          → code-reviewer → security-reviewer → documentation-writer
          → devops → release-manager
```

Dependency (communication) graph — who feeds whom — lives in
`common/roster.py::DEPENDENCIES`. Example: `release-manager` consumes the
outputs of QA, Code Review, Security, Docs and DevOps before drafting the release
and giving a Go/No-Go.

## The brain

Every agent thinks with **Claude** when `ANTHROPIC_API_KEY` is set (model via
`A2A_MODEL`, default `claude-opus-4-8`). With no key it uses a **deterministic
stub**, so the whole team is runnable and fully testable offline / in CI.

## Run it

```bash
cd agents
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Option A — all agents locally (one process each)
python -m agents.run_all            # from repo root: serves ports 8010-8021

# Option B — Docker (agents discover each other by service name)
docker compose -f agents/docker-compose.agents.yml up --build
```

Drive the team (in another shell), from the repo root:

```bash
python -m agents.orchestrator "Add a LinkedIn post-sync feature to the blog admin"
# or a subset:
python -m agents.orchestrator "Fix the flaky SEO SSR test" --roles devops,frontend-dev,qa-engineer
```

Inspect any Agent Card:

```bash
curl -s http://localhost:8011/.well-known/agent.json | jq
```

## Test

```bash
python -m pytest agents/tests -q   # hermetic, offline (no API key needed)
```

## Layout

```
agents/
  common/
    roster.py     # single source of truth: roles, ports, skills, prompts, DEPENDENCIES
    brain.py      # Claude-or-stub reasoning
    executor.py   # generic A2A AgentExecutor (one class powers every role)
    server.py     # builds the Agent Card + A2A app for a role
  serve.py        # run one agent
  run_all.py      # run the whole team locally
  orchestrator.py # PM: A2A client that discovers cards and delegates
  tests/          # A2A protocol + roster tests
  Dockerfile
  docker-compose.agents.yml
```
