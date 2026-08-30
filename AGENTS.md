# AGENTS.md — Hirefolio

Instructions for AI coding agents (GitHub Copilot coding agent, and any other tool that reads
`AGENTS.md`). **`CLAUDE.md` at the repo root is the authoritative, complete AI configuration** —
read it first; this file is the condensed operational summary and never overrides it.
Copilot-specific guidance: `.github/copilot-instructions.md` + `.github/instructions/*.instructions.md`.

## Project

Personal portfolio + blog (public repo `github.com/mavrovde/hirefolio`). Angular 22 workspace
frontend (`frontend/projects/{public,admin,shared}` — public is SSR), FastAPI backend (`backend/`,
Python 3.12, SQLAlchemy 2 async, PostgreSQL 16 + pgvector, Ollama), Docker Compose infra,
LinkedIn → site content pipeline (`scraper/`, `importer/`).

## Build & test

Backend (`cd backend`; venv at `backend/venv`):
```
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/test_mavrov \
HIREFOLIO_GEMINI_API_KEY="" venv/bin/pytest          # needs Postgres on 127.0.0.1:5433; 100% coverage
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
6. Dependency policy: upgrade within current majors by default; breaking majors are separate,
   deliberate efforts. Update `requirements.txt` and `requirements-dev.txt` together.
7. Update `CHANGELOG.md` `[Unreleased]` and relevant docs with every change; Conventional Commits.
   Commit durable lessons to `.claude/skills/lessons-learned/`, not only to private memory.
8. No rogue prod actions. A green `deploy.yml` always means images are **published**; the prod host
   is updated only when the secrets-gated `Roll Out To Prod Host` job ran (#175 — it skips, still
   green, when `DEPLOY_HOST`/`DEPLOY_USER`/`DEPLOY_SSH_KEY` are unset; #112/#156). Check that job
   before claiming prod is updated. Check CodeQL + Dependabot every release.
9. **No irreversible local/infra destruction** (`docker volume rm/prune`, `compose down -v`,
   `system prune`, dropping non-`test_*` DBs, recursive `rm` of data dirs) without explicit user
   authorization naming the resource.
10. **No real API keys / paid-service credentials in any test or CI job** — mock the call or use an
    empty/dummy credential (free local fallback). CI passes `HIREFOLIO_GEMINI_API_KEY: ""`.
11. Every PR needs an independent `pr-reviewer` verdict before merge — no exceptions.

Operational rule (not a numbered CLAUDE.md rule, but non-negotiable in practice): **never run
backend pytest while another suite is running** (`pgrep -f pytest` first — the shared `test_mavrov`
DB clobbers concurrent suites).

### Working discipline

- **Mutation-check tests that pin a fix**: revert the fix and confirm the test fails — a test that
  passes both ways pins nothing (`git stash -- <file>` is a no-op for committed changes; use
  `git checkout origin/main -- <file>`).
- **Signature/behaviour changes need the FULL suite *as CI runs it*** (`pytest -n auto … --cov-fail-under=100`),
  never `-k` — stale mocks and patches of deleted symbols live in other files; caught twice in review,
  once only after reddening `main`, where it had passed every serial local run.
- **Verify gates actually gate**: ask what would fail if the standard were violated right now.
- **Close-the-loop links the PR**: a `Closes #NN` auto-close leaves no record — comment with the PR,
  merge SHA, pipeline result and each acceptance criterion.

> Numbering above mirrors `CLAUDE.md` exactly — the repo cites rules by number, so never renumber
> them here independently.

## Issues & PRs

Work is issue-driven: every issue carries a milestone, one priority label (`P0`–`P3`), and ≥1 area
label. PRs use `Closes #NN`/`Refs #NN` and state how each acceptance criterion is met. Every PR
also carries ≥1 type label (`bug`/`enhancement`/`documentation`/`dependencies`/`security`) + ≥1
area label — same scheme as issues (`gh pr create --label`). The repo is public — never paste
secrets into code, issues, or PRs.
