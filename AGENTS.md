# AGENTS.md — mavrov.de

Instructions for AI coding agents (GitHub Copilot coding agent, and any other tool that reads
`AGENTS.md`). **`CLAUDE.md` at the repo root is the authoritative, complete AI configuration** —
read it first; this file is the condensed operational summary and never overrides it.
Copilot-specific guidance: `.github/copilot-instructions.md` + `.github/instructions/*.instructions.md`.

## Project

Personal portfolio + blog (public repo `github.com/mavrovde/mavrov.de`). Angular 22 workspace
frontend (`frontend/projects/{public,admin,shared}` — public is SSR), FastAPI backend (`backend/`,
Python 3.12, SQLAlchemy 2 async, PostgreSQL 16 + pgvector, Ollama), Docker Compose infra,
LinkedIn → site content pipeline (`scraper/`, `importer/`).

## Build & test

Backend (`cd backend`; venv at `backend/venv`):
```
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/test_mavrov \
GEMINI_API_KEY="" venv/bin/pytest          # needs Postgres on 127.0.0.1:5433; 100% coverage
venv/bin/ruff check . && venv/bin/ruff format --check .
venv/bin/mypy app --ignore-missing-imports --no-error-summary
venv/bin/bandit -r app -ll --skip B101
```

Frontend (`cd frontend`):
```
npm ci
npm run test:coverage    # shared + public + admin, 100% coverage each
npm run build            # build shared before public/admin
```

Full stack: `./manage.sh start|stop|logs` · full verification incl. Docker E2E: `./verify_all.sh`.

## Non-negotiables (full text in CLAUDE.md)

1. Fix root causes — no band-aids, no suppressed errors, no arbitrary `setTimeout`.
2. Tests with every change; coverage stays 100%; regression test for every bug fixed.
3. Deliver via branch → PR → merge. Never push to `main` directly — merging to `main` deploys prod.
4. Typing is law: Pydantic models backend-side, explicit TS interfaces (no `any`) frontend-side.
5. Frontend state = RxJS Observables + `async` pipe (signals only for local state). The public app
   is zoneless: async property mutations don't repaint — use `async` pipe/signals/`markForCheck()`.
   Guard DOM access with `isPlatformBrowser()`.
6. Update `CHANGELOG.md` `[Unreleased]` and relevant docs with every change; Conventional Commits.
7. **Never run backend pytest while another suite is running** (`pgrep -f pytest` first — the
   shared `test_mavrov` DB clobbers concurrent suites).
8. **No real API keys / paid-service credentials in any test or CI job** — mock the call or use an
   empty/dummy credential (free local fallback). CI passes `GEMINI_API_KEY: ""`.
9. **No irreversible local/infra destruction** (`docker volume rm/prune`, `compose down -v`,
   `system prune`, dropping non-`test_*` DBs, `rm -rf` of data dirs) without explicit user
   authorization naming the resource.
10. A green `deploy.yml` run means images are **published, not live on the prod host**
    (issues #112/#156) — never claim prod is updated from a green pipeline alone.
11. Every PR needs an independent review verdict before merge — no exceptions.

## Issues & PRs

Work is issue-driven: every issue carries a milestone, one priority label (`P0`–`P3`), and ≥1 area
label. PRs use `Closes #NN`/`Refs #NN` and state how each acceptance criterion is met. The repo is
public — never paste secrets into code, issues, or PRs.
