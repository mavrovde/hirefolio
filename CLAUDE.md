# CLAUDE.md — mavrov.de

Primary AI configuration for this repository. **Claude (Claude Code) is the main AI tool for
this project.** This file is the single source of truth for how AI assistants work here; the
legacy per-tool rule files (`.cursorrules`, `.windsurfrules`, `.cline.md`, `.geminirules`,
`AI.md`, `.clauderules`) now just point back here.

---

## What this project is

Personal portfolio + blog with semantic search and local AI. A LinkedIn → mavrov.de content
pipeline moves posts (and profile data) into the site.

- **Frontend**: Angular 22 (standalone components, **Signals**, native SSR via `server.ts`),
  TailwindCSS 4, Vitest 4 (unit), Playwright (E2E).
- **Backend**: FastAPI (runs on **Python 3.12** in prod/CI; local dev venv may be 3.13),
  SQLAlchemy 2 async, PostgreSQL 16 + `pgvector`, Ollama (local LLM/embeddings), crewai 1.x.
- **Infra**: Docker Compose (`db`, `ollama`, `backend`, `frontend`, `proxy`, `open-webui`),
  GitHub Actions (`.github/workflows/deploy.yml`) which is the **prod deploy** (push to `main`).

## Repository map

```
backend/    FastAPI app (app/api, app/services, app/models); tests/; conftest.py mocks crewai/langchain
frontend/   Angular 22 workspace — projects/public (SSR visitor app), projects/admin (CSR admin SPA),
            projects/shared (@mavrov/shared lib); Vitest (per-project) + Playwright (public-e2e/admin-e2e)
scraper/    LinkedIn scrapers — scrape-linkedin.js (profile) + scrape-posts.js (posts) → *_data.json
importer/   Standalone LinkedIn → backend importer (POSTs to /api/app/linkedin/import-post)
agents/     A2A multi-agent delivery team (independent of the importer)
proxy/      Reverse proxy config
specs/      Feature specs (planned/done)
```

## Commands (run these; don't guess)

**Backend** (`cd backend`, venv at `backend/venv`):
- Tests: `pytest` (needs Postgres on `127.0.0.1:5433`; `TEST_DATABASE_URL`/`DATABASE_URL` → a `test_*` DB)
- Lint/format: `ruff check .` && `ruff format --check .`
- Types: `mypy app --ignore-missing-imports --no-error-summary`
- Security: `bandit -r app -ll --skip B101`

**Frontend** (`cd frontend`) — Angular workspace, 3 projects (`public`, `admin`, `shared`):
- Tests (100% coverage each): `npm run test:coverage` (all) or `npm run test:{shared,public,admin}`
- Build: `npm run build` (all) or `npm run build:{shared,public,admin}`. `shared` must build before the apps.
- Serve: `npm start` (public, :4200) · `npm run start:admin` (admin, :4300)
- Shared code lives in `@mavrov/shared`; apps consume it via the `SHARED_ENVIRONMENT` +
  `AUTH_TOKEN_PROVIDER` injection tokens (public passes a null token; admin wires it to AuthService).

**Full stack / verify / release**:
- `./manage.sh start|stop|logs` — Docker stack
- `./verify_all.sh` — full suite incl. Docker E2E (⚠️ line ~26 has a hardcoded conda path; make it
  portable before relying on it locally)
- Deploy = **push to `main`** → GitHub Actions builds images + `docker compose -f
  docker-compose.prod.yml up -d`. `release.sh --patch|--minor|--major` bumps version + tags + pushes.

**LinkedIn pipeline** (see `importer/README.md`, `scraper/WORKFLOW.md`):
- Scrape: `cd scraper && PLAYWRIGHT_CHANNEL=chrome HEADLESS=false node scrape-linkedin.js` (profile)
  and `node scrape-posts.js` (posts). Session lives in `scraper/.chrome-profile/` (gitignored).
- Import: `MAVROV_API_URL=... LINKEDIN_IMPORT_TOKEN=... python -m importer [--dry-run] [--publish]`.
  Upserts by LinkedIn URN (idempotent); imported posts are drafts by default.

## Claude Code tooling in this repo

- **MCP servers** (`.mcp.json`): `postgres` (read-only SQL on the pgvector DB), `playwright`
  (browser automation), `github` (PRs/issues). Approve on first use.
- **Subagents** (`.claude/agents/`): `devops-pipeline` (babysit CI after a merge), `backend-dev`,
  `frontend-dev` (reproduce → fix → verify a diagnosis, then deliver via a PR — not a direct push).
- **Pre-push hook** (`.claude/hooks/pre-push-tests.sh`, via committed `.claude/settings.json`): runs
  docs + backend pytest + frontend tests before every `git push`; env-configurable, self-gating.
- **Plugins** (project scope): frontend-design, context7, playwright, pyright-lsp, typescript-lsp,
  security-guidance.
- **Slash commands** (`.claude/commands/`): project flows — `/verify`, `/release`, `/linkedin-sync`.

## Engineering rules (non-negotiable)

1. **Root cause, no band-aids.** Trace a bug to its origin (component → service → API → SQL). No
   arbitrary `setTimeout`, no silently swallowed exceptions, no suppressed type/lint errors.
2. **Tests with every change.** Keep coverage **≥95%** (the project standard is 100%). Cover error
   paths (400/500/timeouts), not just happy paths. Add a regression test for every bug fixed.
3. **Deliver via PR; green before push.** **Never push feature work directly to `main`** — always
   branch → pull request → merge (the merge is the sanctioned prod trigger). Before pushing, run the
   **full** local suite: backend (ruff/format + mypy + pytest) **and** all frontend project tests
   **and** the Docker E2E — not just one part. A shared pre-push hook
   (`.claude/hooks/pre-push-tests.sh`) enforces docs + backend + frontend. Never push code that fails
   a gate; keep the PR description's checklist current.
4. **Typing is law.** Pydantic models for backend schemas; explicit TypeScript interfaces (no `any`)
   mirroring them. All backend I/O is async.
5. **Frontend discipline.** State via Signals (`signal`/`computed`/`effect`). Guard all DOM access
   with `isPlatformBrowser()` (SSR-safe). Components stay dumb; logic lives in injected services.
6. **Dependency policy.** Upgrade to latest **within current majors** by default; breaking majors
   (e.g. Angular, TypeScript) are separate, deliberate efforts. `linkedin-api` stays `2.2.1` (prod
   installs a patched wheel). Update both `requirements.txt` and `requirements-dev.txt` together.
7. **Docs + changelog with code.** Update `README.md` and `CHANGELOG.md` (`[Unreleased]`) as part of
   the change. Conventional Commits (`feat:`/`fix:`/`chore:`/`docs:`), atomic.
8. **No rogue prod actions.** Deploy only via the sanctioned path (merge to `main` / `release.sh`).
   A release is **confirmed only when the `deploy.yml` pipeline is green end-to-end** — babysit the
   run and react to results (fix forward on red), then tag `vX.Y.Z`. **Check GitHub security reports
   (CodeQL + Dependabot) every release** and triage them. Confirm before anything irreversible or
   outward-facing (merging to `main` triggers a prod deploy).

## Execution protocol

Reconnaissance (read the target + its deps + its tests) → blast-radius analysis → define types
first → implement defensively → write/update tests → verify locally (format, lint, type, test).
