# mavrov.de — A2A Agent Team

A team of role-based AI agents that interoperate over the **A2A (Agent2Agent) protocol**.
Each role is an independent **A2A server** exposing an **Agent Card** at
`/.well-known/agent.json` and a JSON-RPC endpoint (`message/send`, `tasks/*`,
SSE streaming). The **Project Manager** is also an **A2A client** that discovers
the specialists via their Agent Cards and delegates work over the wire.

Built on the canonical [`a2a-sdk`](https://pypi.org/project/a2a-sdk/) (0.2.x).

## Roster (16 agents, ports 8010–8025)

The roster below is generated from `common/roster.py` (the single source of truth).

| Role | Key | Port | Purpose |
|------|-----|------|---------|
| Project Manager | `project-manager` | 8010 | Plans & orchestrates the team (A2A client) |
| Solution Architect | `architect` | 8011 | Technical design, interfaces, trade-offs |
| Story Writer | `story-writer` | 8012 | User stories + acceptance criteria |
| Backend Developer | `backend-dev` | 8013 | FastAPI / Python implementation |
| Frontend Developer | `frontend-dev` | 8014 | Angular 22 / TS implementation |
| QA Engineer | `qa-engineer` | 8015 | Test plans, verification, coverage |
| Code Reviewer | `code-reviewer` | 8016 | Correctness / security / quality review |
| LinkedIn Checker | `linkedin-checker` | 8017 | Validates the LinkedIn integration |
| DevOps Engineer | `devops` | 8018 | CI/CD pipeline diagnosis & fixes |
| Security Reviewer | `security-reviewer` | 8019 | Dependabot / CodeQL triage, AppSec |
| Documentation Writer | `documentation-writer` | 8020 | Docs, READMEs, CHANGELOG |
| Release Manager | `release-manager` | 8021 | SemVer bump, release notes, Go/No-Go |
| Spec Analyst | `spec-analyst` | 8022 | Requirements analysis of feature specs |
| Planner / Tech Lead | `planner` | 8023 | Task planning & sequencing |
| Integration Engineer | `integration-engineer` | 8024 | Integrates & verifies backend + frontend work |
| Researcher | `researcher` | 8025 | Flexible up-front research |

## Delivery flow

The PM runs specialists in SDLC order, and each agent receives **focused context
from the roles it depends on** (not just the previous message):

```
researcher → spec-analyst → planner → architect → story-writer
           → backend-dev + frontend-dev → integration-engineer
           → qa-engineer / code-reviewer → security-reviewer
           → documentation-writer → devops → release-manager
```

Dependency (communication) graph — who feeds whom — lives in
`common/roster.py::DEPENDENCIES`. Example: `release-manager` consumes the
outputs of QA, Code Review, Security, Docs and DevOps before drafting the release
and giving a Go/No-Go.

## The brain (LLM backend)

Pluggable via `A2A_LLM_PROVIDER` = `ollama` | `anthropic` | `gemini` | `stub` | `auto`.
**Default: `anthropic` (Claude, `claude-sonnet-4-6`), with prompt caching on** — export
`ANTHROPIC_API_KEY` (or put it in the repo-root `.env`). Set `A2A_LLM_PROVIDER=auto` for the
no-cost path (local Ollama → deterministic stub), or `=ollama`/`=gemini`/`=stub` explicitly.
Model via `A2A_MODEL`. The **stub** keeps the team runnable/testable offline (CI, no key).

Prompt caching (system prompt + tool defs + the tool-loop transcript) is always on for the
Anthropic path. To **verify cache hits**, run with `A2A_LOG_USAGE=1` and watch for
`cache_read=…>0` on calls after the first within the ~5-min TTL.

### Recommended: Ollama (local, no API key)

```bash
export A2A_LLM_PROVIDER=ollama
export A2A_MODEL=qwen2.5-coder:7b        # see model guidance below
export OLLAMA_URL=http://localhost:11434 # default
ollama pull qwen2.5-coder:7b
```

**On Apple silicon, run Ollama NATIVELY** (`brew install ollama` / the app) — it uses
the **Metal GPU** and your **full RAM**. Ollama *inside Docker* on macOS is CPU-only
and capped by Docker Desktop's VM memory (~8 GB by default), which is too small for
7B+ models. If you must use Docker, raise Docker Desktop → Resources → Memory to ≥12 GB.

**Model guidance (this repo's code-centric team):**

| Model | Size | Fit |
|-------|------|-----|
| `qwen2.5-coder:7b` ⭐ | ~4.7 GB | Best on M-series/16 GB — strong code + reasoning |
| `qwen2.5:7b` | ~4.7 GB | If you weight planning/writing over code |
| `llama3.1:8b` | ~4.9 GB | Solid all-rounder |
| `qwen2.5-coder:14b` | ~9 GB | Higher quality; needs ≥24 GB comfortably |
| `llama3.2` (3B) | 2 GB | Quick/low-RAM; limited for deep review |

### Gemini (recommended for autonomous work — supports tools)

```bash
export A2A_LLM_PROVIDER=gemini
export A2A_MODEL=gemini-2.5-pro            # strongest; or gemini-2.5-flash (cheaper, weaker)
export GEMINI_API_KEY="$(security find-generic-password -s gemini-api-key -w)"  # from Keychain
```

Gemini uses **function-calling**, so the full tool-loop (read/write/run/tests) works —
a stronger model than the local 7B, better at clearing the 100% coverage gate.

### Anthropic

`A2A_LLM_PROVIDER=anthropic` (`ANTHROPIC_API_KEY`, `A2A_MODEL=claude-sonnet-4-6` default, or
`claude-opus-4-8` for max). Full function-calling tool-loop supported, with **prompt caching** on the system prompt + tool definitions (ephemeral) to cut cost/latency.

## Run it

```bash
cd agents
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Option A — all agents locally (one process each)
python -m agents.run_all            # from repo root: serves ports 8010-8025

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

## Autonomous feature pipeline

`agents/autonomous.py` runs the **full logged cycle** for a feature:

```
research → spec → plan → design → stories → implement (isolated git worktree)
→ deterministic TEST GATE (fix loop) → code+security review → docs → release decision → finalize
```

```bash
python -m agents.autonomous "Add an uptime field to the stats endpoint"     # -> opens a PR
A2A_AUTORELEASE=1 python -m agents.autonomous "<goal>"                       # -> auto-merge+release
```

Guarantees / safety model:
- **Isolated worktree/branch** — agents write only there, never directly on `main`.
- **Deterministic test gate** — real backend+frontend suites at a configurable coverage floor (**default 95%**, `A2A_COV_MIN`; CI/merge enforces the project 100%);
  trusts exit codes, not the LLM. Red gate ⇒ bounded fix loop ⇒ if still red, abort.
- **Review gates auto-release** — auto-merge happens only if the gate is green
  AND `code-reviewer` + `security-reviewer` APPROVE AND `release-manager` says GO;
  otherwise it downgrades to a **PR for a human**.
- **Every step is logged** to a committed run-log at `docs/agent-runs/<slug>-<ts>.md`,
  including **critical decisions**; the docs-writer also updates the CHANGELOG.
- **Clear commits** — title + body (what/why, change summary, decisions, run-log ref).
- **GitHub/pipelines** — agents use the read-only `gh_cli` tool; DevOps drives the
  CI recovery loop. Mutating git/gh + releases are done only by the deterministic layer.
- **No silent rollback** — if the team can't make CI green after bounded fix
  attempts, `main` is left intact and a **GitHub issue escalates to a human** with
  a clear explanation (what failed, diagnosis, what was tried, current state).

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
    tools.py      # repo tools (read-only + write sets) for the tool-loop
  serve.py        # run one agent
  run_all.py      # run the whole team locally
  orchestrator.py # PM: A2A client that discovers cards and delegates
  intake.py       # specs/inbox watcher: runs the autonomous pipeline per spec
  autonomous.py   # full logged feature cycle (worktree, test gate, PR)
  tests/          # A2A protocol + roster tests
  Dockerfile
  docker-compose.agents.yml
```
