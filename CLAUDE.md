# CLAUDE.md — Hirefolio (repo: mavrovde/hirefolio; the maintainer deploys it at mavrov.de)

Primary AI configuration for this repository. **Claude (Claude Code) is the main AI tool for
this project.** This file is the single source of truth for how AI assistants work here; the
legacy per-tool rule files (`.cursorrules`, `.windsurfrules`, `.cline.md`, `.geminirules`,
`AI.md`, `.clauderules`) now just point back here.

---

## What this project is

Personal portfolio + blog with semantic search and local AI. A LinkedIn → mavrov.de content
pipeline moves posts (and profile data) into the site.

- **Frontend**: Angular 22 (standalone components, **RxJS Observables + `async` pipe** for state,
  native SSR via `server.ts`), TailwindCSS 4, Vitest 4 (unit), Playwright (E2E).
- **Backend**: FastAPI (runs on **Python 3.12** in prod/CI; local dev venv may be 3.13),
  SQLAlchemy 2 async, PostgreSQL 16 + `pgvector`, Ollama (local LLM/embeddings).
- **Infra**: Docker Compose (`db`, `ollama`, `backend`, `frontend`, `proxy`, `open-webui`),
  GitHub Actions (`.github/workflows/deploy.yml`) which is the **prod deploy** (push to `main`).

## Repository map

```
backend/    FastAPI app (app/api, app/services, app/models); tests/; conftest.py mocks heavy native libs
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
- `./verify_all.sh` — full suite incl. Docker E2E (runs backend pytest via `backend/venv` → `python3`;
  override the interpreter with `PYTEST_PYTHON`)
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
- **Hooks** (`.claude/hooks/`, via committed `.claude/settings.json`, both `PreToolUse Bash`):
  `pre-push-tests.sh` runs docs + backend pytest + backend lint/type (ruff check + ruff format --check
  + mypy) + frontend tests before every `git push` (env-configurable: `PREPUSH_RUN_LINT`/
  `PREPUSH_RUN_RUFF`/`PREPUSH_RUN_MYPY` …, self-gating); `guard-destructive.sh` blocks irreversible
  local/infra destruction (rule 9) — command-position aware, bypass one command with
  `GUARD_DESTRUCTIVE=0`.
- **Plugins** (project scope): frontend-design, context7, playwright, pyright-lsp, typescript-lsp,
  security-guidance.
- **Skills** (`.claude/skills/`): `issue-workflow` (issue/PR/milestone/label flow) and
  **`lessons-learned`** — the committed "do-not-repeat" knowledge base (zoneless-CD + SSR-HttpBackend
  traps, pytest local-DB isolation, GHA multi-GB-cache net-negative, SemVer-by-content, green-pipeline
  release rule, destruction guardrail). **Consult `lessons-learned` before** SSR/HTTP/CD changes,
  local pytest, adding a CI cache, a release, or destructive local commands — it exists so we don't
  re-research what we already know.
- **Slash commands** (`.claude/commands/`): project flows — `/verify`, `/release`, `/issue-triage`,
  `/linkedin-sync`.

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
5. **Frontend discipline.** State via RxJS Observables rendered with the `async` pipe (components
   expose `Observable` fields composed with `switchMap`/`catchError`/`shareReplay`, consumed as
   `value$ | async` in templates); RxJS is the **primary** state/streams mechanism. Signals are
   used only sparingly for local component state where they fit (e.g. `blog-post`), not as the
   default. Guard all DOM access with `isPlatformBrowser()` (SSR-safe). Components stay dumb; logic
   lives in injected services.
6. **Dependency policy.** Upgrade to latest **within current majors** by default; breaking majors
   (e.g. Angular, TypeScript) are separate, deliberate efforts. `linkedin-api` stays `2.2.1` (prod
   installs a patched wheel). Update both `requirements.txt` and `requirements-dev.txt` together.
7. **Docs + changelog with code.** Update `README.md` and `CHANGELOG.md` (`[Unreleased]`) as part of
   the change. Conventional Commits (`feat:`/`fix:`/`chore:`/`docs:`), atomic. **Commit durable
   lessons, don't hoard them:** when you learn a hard-won, reusable lesson (a footgun, a non-obvious
   root cause, a "don't do X"), record it in the **in-repo** `.claude/skills/lessons-learned/` as part
   of the change — not only in machine-local private memory, which fresh contexts and teammates can't
   see. Uncommitted knowledge doesn't compound.
8. **No rogue prod actions.** Deploy only via the sanctioned path (merge to `main` / `release.sh`).
   A release is **confirmed only when the `deploy.yml` pipeline is green end-to-end** — and note
   that green means *published AND (once the `deploy` rollout job is active via the `DEPLOY_*`
   secrets) rolled out + health-gated on the live host*; while those secrets are absent, live
   state must be verified manually (`docs/DEPLOYMENT.md`, issues #112/#156). Babysit the
   run and react to results (fix forward on red), then tag `vX.Y.Z`. **Check GitHub security reports
   (CodeQL + Dependabot) every release** and triage them. Confirm before anything irreversible or
   outward-facing (merging to `main` triggers a prod deploy).
9. **No irreversible local/infra destruction.** Never `docker volume rm`, `docker volume prune`,
   `docker compose down -v/--volumes`, `docker system prune`, `docker image prune -a`, `DROP`/recreate
   a **non-`test_*`** database, or a recursive `rm` of a data dir / volume mount (`data`, `pgdata`, `volumes`,
   `ollama`, `open-webui`, `.chrome-profile`, `linkedin_cookies`, …) **without explicit user
   authorization that names the resource**. A backup is **not** a substitute for authorization. Prefer
   non-destructive paths (bump the image to match the volume schema, migrate, or leave it). Only
   `test_*` databases may be dropped autonomously (pytest teardown). Defense-in-depth: the
   `.claude/hooks/guard-destructive.sh` PreToolUse hook blocks these patterns (bypass a single
   authorized command with `GUARD_DESTRUCTIVE=0` prefixed). Origin: the #91 incident (a subagent ran
   `docker volume rm mavrovde_open-webui_data` on its own initiative).
10. **NEVER use real API keys or paid-service credentials in tests or CI — STRICTLY FORBIDDEN.** No
    unit test, integration/E2E test, fixture, seed, or CI test stack may authenticate to a paid,
    metered, or rate-limited external service (any API that bills or consumes quota per call) with a
    **real** credential. Every such call MUST be either **(a) mocked/stubbed at the test boundary**
    (e.g. `page.route` in Playwright, monkeypatch/fake in pytest) **or (b) routed to a free local
    fallback** by supplying an **empty or dummy** credential so no billable request is made. CI test
    jobs MUST inject empty/placeholder credentials into the test stack — **never** a real secret
    (`${{ secrets.* }}`). Real credentials belong **only** to the production runtime environment,
    never to a test or CI job. Before writing or running any test/CI path, verify it cannot reach a
    paid service with a live credential. **Rationale:** a real key wired into an automated test fires
    on *every* pipeline run — causing silent, unbounded, recurring cost and quota exhaustion — and
    needlessly exposes the credential to CI logs. Treat any such wiring as a critical bug to fix, not
    to run. (In this repo: CI passes `GEMINI_API_KEY: ""` so the E2E falls back to the local Ollama;
    paid-API specs are also mocked.)
11. **Independent review gate — EVERY PR requires a `pr-reviewer` verdict before merge. NO
    EXCEPTIONS.** No pull request is merged until an **independent** `pr-reviewer` review (an APPROVE
    verdict) is **posted to the PR**. Green CI, a passing local/pre-push suite, and validation by the
    implementing dev agent (`backend-dev`/`frontend-dev`) are **necessary but NOT sufficient** — none
    of them is an independent review. This gate applies to **every** PR with **no carve-outs**:
    hotfixes and emergencies, dependency bumps, trivial/one-line/CI/docs changes, and changes the user
    directed in real time. **"The user was directing it" and "a dev agent validated it" are NOT
    substitutes** for the review verdict. If a change is urgent, the review is **expedited, not
    skipped**. The only state that authorizes a merge is: **all gates green AND a posted `pr-reviewer`
    APPROVAL**. Therefore every merged PR must carry a visible review verdict as its audit trail; if
    one was ever merged without it, post a retrospective review and fix-forward on any finding.
    (`pr-reviewer` posts a `gh pr review`/`gh pr comment` verdict; same-identity `--approve` may be
    blocked, so a clear COMMENT verdict counts.)

## Issue tracking, milestones & labels (development flow)

The repo is **PUBLIC** (`github.com/mavrovde/hirefolio`). This flow is the shared source of truth
for issue-driven work — humans and AI agents both follow it.

1. **Issues are the project notebook.** Every idea, plan, bug, deferred fix, shipped milestone, and
   research decision lives as a GitHub issue on `mavrovde/hirefolio` — never only in chat or personal
   memory. Register work as an issue up front; **close-the-loop** when it lands (see rule 7).
2. **Full issue template (every issue):** Summary → Why it matters → Impact (project / developers /
   visitors) → Current state (grounded, cite `path:line`) → Proposed action → **Acceptance criteria**
   (checkable list) → **How to verify (test steps)** → Links.
3. **No orphan issues.** Every issue MUST carry a **milestone** (theme), a **priority** label
   (`P0-critical` / `P1-high` / `P2-medium` / `P3-low`), and **≥1 area label**.
4. **Milestones are reusable thematic buckets, NOT per-version.** Reuse an existing theme for similar
   work (e.g. every dependency task → *Dependency modernization*); add a new theme milestone only for
   a genuinely new theme. Current buckets:
   - **Dependency modernization** — dep upgrades + upstream-blocked bumps.
   - **Security & hardening** — vuln remediation, rate-limiting, secret hygiene.
   - **Reliability & bug fixes** — flakes, schema/data drift, session bugs.
   - **CI/CD, tooling & docs** — pipeline, gates, tooling, doc accuracy.
   - **Content & localization** — content + translations.
   - **Transfer to general portfolio** — the product/template transformation.
5. **Label scheme** = type + area + priority:
   - type: `bug` / `enhancement` / `documentation` / `dependencies` / `security`
   - area: `backend` / `frontend` / `infra` / `ci-cd` / `performance` / `tech-debt` /
     `architecture` / `content` / `i18n`
   - priority: `P0-critical` / `P1-high` / `P2-medium` / `P3-low`
6. **PRs link issues.** Use `Closes #NN` / `Fixes #NN` for issues a merge resolves, `Refs #NN` for
   partial/related work. State how the PR satisfies each of the issue's **acceptance criteria**; keep
   the PR checklist current.
7. **Close-the-loop (verify before closing).** When work lands, comment on the issue with what was
   done + links, **verify against its acceptance criteria / test steps**, then close it (or note the
   remaining status if partial). Never close on assumption. **A `Closes #NN` auto-close is NOT
   close-the-loop** — it leaves no visible record, so the issue reads as "just closed" to anyone
   later. Always post a comment naming **the PR, the merge SHA, the pipeline result, and each
   acceptance criterion with how it was verified**; if a criterion is unmet, say so and keep the
   issue open rather than closing optimistically.
   **Report what you measured, not what you expect.** Several claims in this repo's history were
   wrong until checked: "the release deploys correctly" (the images were private), "a regression
   fails the suite" (it passed both ways), "15 cases" (there were 18), "dependency-free" (it needed
   npm). If you assert a number or an outcome, run the thing that produces it first.
8. **No secrets in public issues/PRs.** Never paste credentials, tokens, private keys, or
   step-by-step live-exploit instructions. Reference config locations (`path:line`) instead of the
   secret values.
9. **Tooling.** The `github` MCP server + `gh` CLI manage issues/PRs/milestones/labels; the
   `security-guidance` plugin supports security triage. The **`issue-workflow` skill**
   (`.claude/skills/issue-workflow/`) captures this end-to-end flow with copy-paste `gh` commands;
   `/issue-triage` sweeps the backlog for orphan issues.

## Execution protocol

Reconnaissance (read the target + its deps + its tests) → blast-radius analysis → define types
first → implement defensively → write/update tests → verify locally (format, lint, type, test).
