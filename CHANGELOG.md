# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Public app committed to zoneless change detection** (#105). The public build ships no `zone.js`
  polyfill (`frontend/angular.json`) yet declared no change-detection driver, so async property
  mutations silently never repaint in the browser (the #94 class) — fine in unit tests that bundle
  `zone.js`, frozen live. `app.config.ts` now provides `provideZonelessChangeDetection()` and the
  components that mutated plain template props in async callbacks trigger CD explicitly via
  `ChangeDetectorRef.markForCheck()` (`cv.component`, `header.component`, `blog.component`'s browser
  fetch/fallback paths). The dead `NgZone.run(...)` wrappers in `blog.component` (NgZone is a no-op
  under zoneless) were removed. A `public-e2e` guard asserts a purely-async region — the footer
  uptime counter (`setInterval` + `markForCheck`) — actually advances live.
- **Real HTTP 404 for unknown blog slugs on SSR** (#109). `blog-post.component` resolved a
  missing/unpublished slug to a graceful not-found panel but SSR served it `200` (a soft-404 that
  pollutes crawler indexes). When the view resolves to not-found on the **server**, the component now
  sets the outgoing SSR response status to `404` via the `RESPONSE_INIT` injection token
  (`@angular/core`), and marks the page `noindex` with a "Post not found" title (new
  `SeoService.setNotFound()`) on both platforms. Known slugs still return `200`; the client-rendered
  not-found panel is unchanged. Guarded by a `public-e2e` assertion (`404` for an unknown slug, `200`
  for known routes).
  lever). Investigation of why `Build Backend Image` stayed ~5min despite an existing `type=gha`
  layer cache found the base stage running `npx playwright install --with-deps chromium` (plus a
  Node.js 20 install + `npm i -g playwright dotenv cross-env`) — **~500MB+ of browser tooling the
  FastAPI backend never uses at runtime**. Verified exhaustively: LinkedIn ingest uses the pure-HTTP
  Python `linkedin-api` client (`app/services/linkedin.py`, docstring "no Node.js"), the entrypoint
  is Python/alembic, `main.py` uses the Python `python-dotenv`, and the only subprocess is `pg_dump`
  (postgresql-client) — nothing imports/execs Node, Playwright, or Chromium (the "Playwright scraper"
  references were stale docstrings, now corrected). Removing it shrinks the image by ~500MB+, cuts the
  dominant base-stage build step, and shrinks the `type=gha` cache (whose slow restore of that giant
  layer was the "5min despite cache" cause — same net-negative pattern as #72/#78), with a security
  bonus (smaller attack surface). Validated against the full Docker E2E (backend builds, starts, and
  serves the stack with no Playwright). `libpq5`/`postgresql-client`/`curl` retained.

### Docs
- **Fold the v1.8.1 SSR/zoneless lessons into the agent charters** (`.claude/agents/frontend-dev.md`,
  `.claude/agents/pr-reviewer.md`, `agents/common/roster.py`). Documented the three hard-won gotchas
  from the #25/#94 fixes so future agents catch them at review/implementation time instead of at the
  deploy E2E: (1) the public app is effectively **zoneless** (no `zone.js` polyfill) so async
  property mutations need the `async` pipe / signals / `markForCheck()` to repaint (#94 class); (2)
  SSR URL rewrites belong in an `HttpBackend` delegating to `HttpXhrBackend`, never `FetchBackend`
  (#25 / reverted #84); (3) changing a user-visible behavior means grepping ALL e2e specs for the old
  assertion (the #108→#110 stale-test fix-forward). Also corrected `pr-reviewer.md`'s stale
  "Signals-primary" claim to the actual RxJS-Observables-+-async-pipe reality (rule 5).

## [1.8.1] - 2026-07-29

### Changed
- **Parallelize the CI `Backend Tests` job with `pytest-xdist` (`-n auto`)** (#91, lever 3). The
  backend suite ran serially (`deploy.yml`), making it the ~5.2-min head of the deploy critical
  path. It now runs across all available cores. The single shared Postgres service (one DB) made
  naive parallelism collide on unique constraints (`ux_post_slug_lang` / `ix_post_source_urn`), so
  `backend/conftest.py` now gives **each xdist worker its own database**: it derives a per-worker DB
  name from `PYTEST_XDIST_WORKER` (`test_mavrov_gw0`, `_gw1`, …), creates it if absent via asyncpg
  against the `postgres` maintenance DB in `pytest_configure`, points the async engine + schema
  `create_all` at it, and drops it (`WITH (FORCE)`) at session end. Serial runs (no `-n`) and the
  xdist controller keep the original single-shared-DB behavior unchanged. `pytest-cov` aggregates
  coverage across workers, so the 100% gate is preserved. Added `pytest-xdist==3.8.0` to
  `requirements-dev.txt`. Measured in real CI (deploy run 30404645861): the `Backend Tests` job
  dropped **298s → 191s (−36%)**, coverage aggregated at 100%, zero correctness regressions.
- **CI: remove the redundant standalone "Proxy Verification" job** (#91, lever 2). The
  `proxy-startup-test` job spun the full prod stack up a **second time** just to grep the Nginx
  start banner, and all four `publish-*` jobs blocked on it — pure critical-path waste (~284s). The
  `e2e-tests` job already starts the same stack (including `global_proxy`) and waits for HTTP
  200/302 on `:80` (a stronger check); its unique log-grep assertion is now folded into `e2e-tests`
  as a "Verify Proxy Startup (Smoke)" step, and `publish-{backend,frontend,admin-frontend,proxy}`
  now depend on `e2e-tests` directly. No verification dropped. Measured in real CI (deploy run
  30406891756): end-to-end deploy wall-clock **29.45min → 24.85min (−15.6%)**. Remaining #91 lever:
  the ~5.5-min backend-image build (the Ollama-weights and base-image caches were both measured
  net-negative and reverted, #78/#72).

### Fixed
- **Blog deep-links no longer flash back to the home page on hydration; the public site's
  `/stats/public` browser fetch keeps working** (#25, #94). The SSR relative→absolute URL rewrite
  (`/api/...` → `http://backend:8000/...`) lived in an `HttpInterceptorFn`, which runs *before*
  Angular's HTTP transfer-cache interceptor — so the server keyed the transfer cache on the
  *rewritten* absolute URL while the browser keyed it on the *relative* URL. The keys never matched,
  so on hydration the browser re-fetched every request; a transient failure of the needless blog
  re-fetch hit `BlogPostComponent`'s `catchError`, which navigates to `/` — the "flash to home". The
  rewrite now lives in a custom `HttpBackend` (`SsrHttpBackend`), which runs *after* the transfer
  cache has keyed the original (server/client-identical) relative URL, so the browser reuses the SSR
  response instead of re-fetching. Unlike the first attempt (reverted #84, which delegated to
  `FetchBackend` and broke the only genuine browser fetch, `GET /api/app/stats/public` →
  `net::ERR_FAILED`), this backend delegates to **`HttpXhrBackend`** — the exact backend the app has
  always used on both platforms — so the browser dispatch is byte-identical to the long-working
  baseline and #94 cannot regress. Removed the old `ssr.interceptor.ts`. Follow-up: `BlogPostComponent`
  now resolves a genuine 404 / transient fetch error to a **graceful "post not found" panel** instead
  of `router.navigate(['/'])` (the old home-bounce, now removed) — a `vm$` of `loading|found|notfound`
  rendered via the `async` pipe. Added a **retries:0** E2E guard (`blog-display.spec.ts`) that asserts a
  direct `/blog/:slug` load renders the post and keeps the URL (no flash-to-home) and that an unknown
  slug shows the not-found panel without redirecting home; the existing create→view E2E tests now poll
  the public API until the new post is queryable, removing the brand-new-post propagation flake (#107).
- **Footer system-stats now render on the public site (backend version, uptime, memory)** (#94). The
  full Docker E2E surfaced a second, deeper root cause behind the footer showing `BE: vUnknown`: the
  public app bundles **no `zone.js`** (`angular.json` has no `polyfills` entry) and declares no
  zoneless change-detection provider, so it runs effectively zoneless — yet `SystemStatsComponent`
  updated **plain properties** inside `subscribe`/`setInterval` callbacks, which never trigger change
  detection, leaving the footer frozen at its SSR-initial values (`vUnknown`, `00:00:00`, `24MB`).
  The `/api/app/stats/public` fetch itself was fine (HTTP 200); only the repaint was missing. Fixed
  by injecting `ChangeDetectorRef` and calling `markForCheck()` after each async mutation — the same
  pattern the sibling `blog.component` already uses. (The broader "no CD driver configured" ambiguity
  is tracked separately for a deliberate zone-vs-zoneless decision.) Both #25 and #94 were validated
  against the full Docker E2E stack (`footer-stats` + blog specs) before merge, not just unit tests.
- **LinkedIn session now persists across container recreates/deploys** (#44). The saved LinkedIn
  login session was stored under `/tmp/linkedin_cookies` inside the backend container — part of the
  ephemeral container layer — so every deploy or restart wiped it and forced the admin to
  re-authenticate. The session directory is now driven by the new env-overridable
  `LINKEDIN_COOKIES_DIR` setting (defaulting to `/data/linkedin_cookies`) and is backed by a new
  `linkedin_cookies` named volume mounted on the `backend` service in both `docker-compose.yml` and
  `docker-compose.prod.yml`, so the saved session survives container recreation. The `/linkedin/status`
  response now also returns a human-readable `message` explaining whether a session is active.
- **E2E: correct the stale `blog-interactions` invalid-slug test to the shipped graceful not-found
  behavior** (Refs #25). PR #108 (issue #25, criterion 3) removed the old home-bounce so
  `BlogPostComponent` now renders a "post not found" panel while staying on `/blog/:slug`, but the
  leftover `should redirect to home for invalid slug` test in
  `frontend/e2e/public/blog-interactions.spec.ts` still asserted the removed redirect and failed the
  public-e2e shard deterministically. Retitled it to
  `should show a graceful not-found panel for an invalid slug (no home redirect)` and aligned its
  assertion with the authoritative `blog-display.spec.ts` guard — it now expects the
  `post-not-found` panel visible and the URL to stay on `/blog/:slug`. Test-only; no app change.

### Docs
- **Reconcile the root `agents/` A2A roster prompts with the `.claude/agents/` charters** (#99).
  The A2A delivery-team `system_prompt`s in `agents/common/roster.py` predated the richer Claude
  Code subagent charters added in #89 and had drifted. Enriched the overlapping role prompts with
  the hard-won guidance from the matching charters: `code-reviewer` ← `pr-reviewer` (mandatory
  test-coverage + user/edge-case analysis — "coverage executed ≠ behavior asserted" — and a clear
  severity-tagged APPROVED/REJECTED verdict); `release-manager` ← `release-manager` (SemVer bump by
  content, never default to minor; the CHANGELOG `[Unreleased]`→version rotation trap; tag on the
  full SHA; `deploy.yml` has no concurrency guard so serialize; babysit to green, fix-forward on
  red); `security-reviewer` ← `security-triage` (pull & triage CodeQL + Dependabot real-vs-noise,
  file grounded issues, verify a release's fixed alerts show `fixed`, no exploit details in a public
  repo); `spec-analyst`/`story-writer` ← `issue-author` (ground every claim in real code with
  `path:line`, the full issue template + milestone/priority/area labels). Also fixed factual drift:
  the `frontend-dev` prompt no longer claims Angular "signals" (the app uses RxJS Observables + the
  `async` pipe, per #29 — Signals only sparingly for local state), and `PROJECT_PLAYBOOK` now states
  Python **3.12** in prod/CI (dev venv may be 3.13) and adds the lesson that SSR/`HttpBackend`/
  interceptor/transfer-cache changes must be validated against the full Docker E2E before merge (the
  v1.8.0 #84 revert). Prompt strings only — no change to role keys, ports, dependencies or the
  A2A architecture; the `agents/tests/` suite (55 tests) still passes.

### Reverted
- **Reverted the Ollama model-weights CI cache** (#78). After it deployed, before/after
  measurement showed it made the `E2E Tests (Docker Stack)` job **~56s slower** (8m20s → 9m16s):
  the cache-hit path cost ~53s (restore 38s + pre-load 15s) but saved only ~11s of model pull —
  the ~3.6 GB GitHub-cache transfer costs as much as re-pulling the models from Ollama's registry,
  and it consumed ~3.6 GB toward the 10 GB repo cache limit. Same self-defeating pattern as the
  base-image cache (#72/#76). Removed the cache steps + `.github/ollama-models.txt`; the real
  pipeline bottleneck is the sequential critical path (tests → build → E2E → proxy), tracked with
  concrete levers in #91.

## [1.8.0] - 2026-07-26

### Fixed
- **Schema drift: Alembic is now the sole, authoritative schema-management mechanism** (#46).
  `app/main.py` no longer calls `Base.metadata.create_all` or runs ad-hoc `ALTER TABLE cv_requests`
  checks at startup; `backend/docker-entrypoint.sh` self-adopts the database into Alembic on every
  container start — no manual step required — before the app starts. It detects which of three
  states the DB is in (a plain `asyncpg` check for `alembic_version` + a known core table): a fresh
  DB just gets `alembic upgrade head`; a DB that predates Alembic (built by the old `create_all` —
  today's prod case) is first stamped at the baseline revision (no DDL) and then upgraded to head,
  avoiding an "object already exists" crash; a DB already tracked by Alembic just gets `upgrade
  head` (a no-op at head). Replaced the previously disjoint/incomplete migration history — the
  top-level `migrations/00N_*.py` scripts (never even on Alembic's discovery path) and the
  `migrations/versions/*` chain (incremental diffs that assumed tables already existed via
  `create_all` and could never run against an empty database) — with a single `baseline0001`
  revision that creates the full current schema (`users`, `cv_documents`, `cv_requests`, `posts`
  incl. pgvector `embedding` and the partial unique index on `source_urn`, `profile_snapshots`).
  Verified byte-identical (via `pg_dump --schema-only`) to what `create_all` previously produced.
  Also fixed `migrations/env.py` (missing `sys.path` bootstrap + missing model imports) and
  `app/models/__init__.py` (missing `User` import), which silently left autogenerate blind to most
  of the schema. Added a CI `backend-migrations` job that exercises the real entrypoint against a
  simulated pre-Alembic DB and a fresh DB (each re-run to confirm idempotency), plus `alembic check`
  (drift guard), on every push to `main`.

### Reverted
- **Reverted the #25 blog-post SSR routing fix** (and its follow-up #94 `withFetch()` change).
  The #25 approach overrode Angular's `HttpBackend` with a custom `SsrHttpBackend` (delegating to
  `FetchBackend`); in the prod E2E this deterministically broke the public site's only genuine
  browser-side fetch (`GET /api/app/stats/public` → `net::ERR_FAILED`), blocking the deploy — and
  adding `withFetch()` did not resolve it. Restored the prior interceptor-based SSR URL rewriting
  (browser HttpClient back on the XHR backend). Issue #25 is reopened to be redone with a
  browser-safe approach validated against the full E2E stack before merge.

### Security
- **Rate-limited the public `GET /api/app/profile` endpoint** (#47): a small, self-contained
  in-memory sliding-window limiter (`backend/app/services/rate_limit.py`, no new dependency)
  rejects excess requests per client IP with `429 Too Many Requests`; the limit/window are
  configurable via `Settings.profile_rate_limit_requests`/`profile_rate_limit_window_seconds`
  (default 100 requests/60s — generous enough that normal browsing/SSR is never affected).
- **Sanitized legacy LinkedIn admin error responses** (`backend/app/api/linkedin.py`, #47): the six
  handlers that used to interpolate the raw caught exception into the client-facing `detail`
  (`login`, `profile-sync`, `posts`, `transfer-post`, `transfer-posts`) now log the full exception
  server-side (`logger.exception`) and return a generic, non-revealing message to the client,
  matching the pattern already used by the newer `import-post`/`import-posts-json` endpoints.

### Changed
- **Pre-push hook now runs backend lint/type (ruff + mypy), matching CI** (#48). Added a
  backend lint/type leg to `.claude/hooks/pre-push-tests.sh` running `ruff check .`,
  `ruff format --check .`, and `mypy app --ignore-missing-imports --no-error-summary` from
  `backend/` (venv), so lint/format/type failures are caught at `git push` instead of only in CI's
  `Backend Lint & Format` / `Backend Type Check` jobs. Env-gated (`PREPUSH_RUN_LINT` default on,
  plus granular `PREPUSH_RUN_RUFF` / `PREPUSH_RUN_MYPY`); the `deny` reason and script header now
  mention the leg. Self-gating (non-`git push` commands still pass instantly) unchanged.
- **Parameterized deployment & infra for a new owner** (#60). Externalized every owner-specific
  infra literal behind env/config so a forker deploys by editing only `.env`/repo variables — no
  source edits. A new root [`.env.example`](.env.example) documents each knob.
  - **Container images:** `docker-compose.yml` dev image names now use the same
    `${IMAGE_REPO:-mavrovde}-<svc>` scheme as prod (`${IMAGE_REPO:-maverickde/mavrov.de}-<svc>`);
    `deploy.yml` publishing is overridable via the `REGISTRY` / `IMAGE_NAME` repository variables
    (defaults keep `ghcr.io/${{ github.repository }}` unchanged for the canonical repo).
  - **Proxy `server_name`:** `proxy/default.conf` became `proxy/default.conf.template`, rendered at
    container start by `entrypoint.sh` (envsubst) from `PUBLIC_SERVER_NAME` / `ADMIN_SERVER_NAME`
    (defaults preserve the canonical hostnames). (Admin-allowlist hardening is deferred to #86 so
    prod admin access is unchanged here.)
  - **Postgres port:** the `5433` literal became the `POSTGRES_PORT` env knob across both compose
    files (PGPORT, host mapping, healthcheck, `DATABASE_URL`).
  - **`verify_all.sh`:** replaced the hardcoded conda python path with a portable interpreter
    (`backend/venv` → `python3`, override via `PYTEST_PYTHON`); updated `.claude/commands/verify.md`.
  - **Agents:** `agents/autonomous.py` and `agents/common/tools.py` derive the repo root at runtime
    (no `/Users/maverick` absolute paths); `A2A_REPO`/`A2A_BACKEND_BIN`/`A2A_BACKEND_PYTHON` override.
- **CI: pinned & cached third-party base images** (#72, PR #76). Added `.github/base-images.txt`
  as the single source of truth (pinned `ollama/ollama:0.5.7`, `open-webui:v0.5.10`,
  `pgvector/pgvector:pg16`, matching prod compose — removed the `:latest` drift) and replaced both
  `Pull Standard Images` steps with an `actions/cache` restore + `docker load`/`save`, so the base
  images download once instead of every run.

### Docs
- **Corrected `CLAUDE.md` frontend state-management guidance** (#48, #29). Rule #5 "Frontend
  discipline" and the project-description bullet now describe the pattern the code actually uses —
  RxJS Observables + the `async` pipe as the **primary** state/streams mechanism (Signals are used
  only sparingly for local component state, e.g. `blog-post`), instead of implying Signals-first
  state; SSR/`isPlatformBrowser()`/dumb-component guidance retained.
- **Codified the issue/milestone/label development workflow into repo config** (#74, PR #75):
  a new `CLAUDE.md` section, `backend-dev`/`frontend-dev`/`devops-pipeline` role updates, a committed
  `.claude/skills/issue-workflow` skill, and a `/issue-triage` command — shared across devices and
  developers.

## [1.7.1] - 2026-07-26

### Security
- **Removed mistakenly-committed TLS certificate files** (`proxy/ssl/fullchain.pem`,
  `proxy/ssl/privkey.pem`) from the (public) repository and added `proxy/ssl/` to `.gitignore`.
  The certificate was already revoked (no live exposure), and the files were orphaned — the proxy
  `Dockerfile` never copied them, no compose service mounts them, and `proxy/entrypoint.sh`
  self-signs a dev cert when none is present, so removal has no runtime effect. Real TLS material
  is provided at runtime (host mount / deploy secret), never committed. Closes #64.

### Changed
- **Backend dependency modernization sweep** (fix-forward on the `ruff` revert from #56;
  closes #54). Re-verified every pinned backend package against latest: `fastapi` 0.140.0,
  `uvicorn` 0.51.0, `sqlalchemy` 2.0.51, `asyncpg` 0.31.0, `pgvector` 0.5.0, `alembic` 1.18.5,
  `httpx`/`respx` 0.28.1/0.23.1, `python-jose` 3.5.0, `passlib` 1.7.4, `python-multipart`
  0.0.32, `Pillow` 12.3.0, `setuptools` 83.0.0, `crewai` 1.15.6, `langchain-openai` 1.4.1,
  `google-genai` 2.14.0, `pytest`/`pytest-asyncio`/`pytest-cov`/`pytest-mock`
  9.1.1/1.4.0/7.1.0/3.15.1, `mypy` 2.3.0, `bandit` 1.9.4 were all already at latest (no changes
  needed). `linkedin-api` stays hard-pinned at `2.2.1` (patched wheel).
- **`ruff` 0.15.2 → 0.16.0, with a real migration** (closes #54). Ruff 0.16 expands its
  *default* enabled rule set from ~62 to ~416 rules. Added an explicit `[tool.ruff.lint]`
  `select` in `backend/pyproject.toml` that pins today's default rule set (413 codes, grouped
  and commented by originating linter) so a future ruff release can't silently change our
  effective lint config again. Of the ~592 resulting findings: ~450 were auto-fixed
  (`ruff check . --fix`, mostly import sorting and `pyupgrade` modernization); real
  correctness/observability issues were fixed at the root — `logger.exception(...)` instead of
  `logger.error(..., exc_info=True)` (`G201`), module loggers instead of the root logger
  (`LOG015`), timezone-aware `datetime.now(UTC)` (`DTZ005`), `asyncio.to_thread(...)` for
  blocking file reads in async startup code (`ASYNC230`), narrowed `pytest.raises(...)` in
  tests (`B017`), a swallowed vector-search exception now logged (`S110`), mutable default
  arguments removed (`B006`), and several small `TRY`/`SIM`/`PERF`/`RUF`/`FURB`/`C4` fixes.
  Three rules are deliberately ignored with documented rationale in `pyproject.toml`:
  `BLE001` (this codebase's intentional broad error-boundary pattern — every site still logs
  or re-raises), `TRY002` (a bespoke exception hierarchy is disproportionate for this app's
  size), and `SIM117` (collapsing nested `with` blocks would hurt readability at several
  test-double and long-async-body call sites). Added
  `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls` for FastAPI's `Depends`/`File`/etc.
  so `B008` no longer false-positives on the framework's documented DI pattern. Removed the
  `ruff >=0.16.0` dependabot `ignore` added in #56 now that the explicit pyproject config
  protects future bumps.
- **`crewai` re-verified at latest (1.15.6)** (refs #52): still pins `pydantic<2.13` and (via
  `instructor`) `rich<15.0.0`, so `pydantic` and `rich` stay held at their current floors
  (`pydantic>=2.12.5`, `rich>=13.0.0,<15.0.0`) — unchanged from before this sweep. #52 stays
  open until a future crewai release relaxes these pins.
- **`backend/Dockerfile` stays on `python:3.12-slim`** (refs #53): `lxml` (pulled in
  transitively by the hard-pinned `linkedin-api==2.2.1`, which requires `lxml<6.0.0`) has no
  Python 3.14 wheel and its sdist fails to build without `libxml2`/`libxslt` dev headers — no
  change needed here, base image was already 3.12.
- **Frontend dependency sweep** (Dependabot #33/#34/#36/#37): `@types/node` `^22.20.1` →
  `^26.1.1`, `jsdom` (Vitest DOM env) `^27.4.0` → `^29.1.1`, `frontend/Dockerfile`
  `node:24-alpine`/`node:24-slim` → `node:26-alpine`/`node:26-slim`, and
  `frontend/Dockerfile.admin` `nginx:1.27-alpine` → `nginx:1.31-alpine`. Verified with
  `npm run test:coverage` (100% across `shared`/`public`/`admin`), `npm run build`, and local
  `docker build` of both Dockerfiles.
- **Comprehensive frontend dependency refresh.** Pinned `@angular/animations`, `@angular/common`,
  `@angular/compiler`, `@angular/core`, `@angular/forms`, `@angular/platform-browser`,
  `@angular/platform-server`, `@angular/router`, `@angular/cli`, `@angular/compiler-cli`,
  `@angular/platform-browser-dynamic`, and `@angular/ssr` from `^22.0.0` to the latest published
  Angular 22 patch, `^22.0.8` (matching the already-current `@angular/build`). Audited every
  other frontend dependency (`ng-packagr`, `express`, `rxjs`, `tslib`, `zone.js`,
  `@analogjs/vite-plugin-angular`, `@playwright/test`, `@tailwindcss/postcss`/`tailwindcss`,
  `@types/express`, `@types/node`, `@vitest/browser-playwright`, `@vitest/coverage-v8`, `jsdom`,
  `stylelint`/`stylelint-config-standard`, `undici`) against their published `latest` dist-tag —
  all were already at their true latest version (a recent sweep had already landed them), so no
  further bump was needed for those. Verified with `npm run test:coverage` (100% across
  `shared`/`public`/`admin`), `npm run build`, and local `docker build` of both Dockerfiles.
  **Held back:** `typescript` stays on `~6.0.3` — `@angular/compiler-cli@22.0.8`'s
  `peerDependencies` requires `typescript: ">=6.0 <6.1"`, and `6.0.3` is already the newest
  version in that range (latest published `typescript` is `7.0.2`, which Angular 22 does not
  support). `undici` stays on `^7.29.0` — `jsdom@29.1.1` depends on `undici@^7.25.0` and its
  internal `jsdom-dispatcher.js` requires a module path (`undici/lib/handler/wrap-handler.js`)
  that `undici@8.x` removed/renamed; overriding to `undici@^8.9.0` breaks every DOM-environment
  test with `Cannot find module 'undici/lib/handler/wrap-handler.js'` (`7.29.0` is the latest
  `7.x` release). Pre-existing `npm audit` findings (`@hono/node-server`/`@modelcontextprotocol/sdk`
  via `@angular/cli`'s MCP tooling, and `brace-expansion`/`ts-morph` via
  `@analogjs/vite-plugin-angular`) are unchanged by this sweep; `npm audit fix --force` would
  downgrade `@angular/cli` to `21.x` and `@analogjs/vite-plugin-angular` to a pre-release, both
  regressions, so they're left for a deliberate follow-up.
- **Backend dependency sweep** (Dependabot #38/#40/#42): `pytest` 9.0.3→9.1.1, `pytest-asyncio`
  1.3.0→1.4.0, `pytest-cov` 7.0.0→7.1.0, `mypy` 1.19.1→2.3.0, `bandit` 1.9.3→1.9.4,
  `google-genai` 1.75.0→2.14.0. `pydantic` (#39) and `rich` (#41) bumps were held back:
  `crewai==1.15.6` pins `pydantic<2.13` and its `instructor` dependency pins `rich<15.0.0`, so
  both would break the dependency graph. `ruff` 0.15.2→0.16.0 was also held: 0.16.0 changed its
  default lint rule set from ~62 to ~416 rules, surfacing 592 unrelated findings across the
  codebase — out of scope for a dependency-only sweep. The backend `Dockerfile` base image bump
  to `python:3.14-slim` (#32) was held too: `lxml` (pulled in by `linkedin-api`) has no Python
  3.14 wheel yet and its sdist build fails (`Please make sure the libxml2 and libxslt development
  packages are installed`).

### Fixed
- **Reverted `ruff` 0.16.0 (Dependabot #55) that broke `main`.** Dependabot auto-merged a
  recreated group PR bumping `ruff` 0.15.2→0.16.0; 0.16's expanded default rule set failed
  `ruff check .` on the existing codebase (`I001`, …), turning the prod deploy red. Pinned back
  to `0.15.2` and added a dependabot `ignore` for `ruff >=0.16.0` so it can't re-open the loop.
  The deliberate 0.16 migration (pin an explicit `[tool.ruff.lint] select`, then triage ~592
  findings) is tracked in #54.

### Held
- `pydantic` (`>=2.13.4` available) and `rich` (`15.0.0` available) — blocked by
  `crewai==1.15.6`'s own `pydantic<2.13,>=2.11.9` pin and its `instructor` dependency's
  `rich<15.0.0,>=13.7.0` pin (verified via `pip install crewai==1.15.6 --dry-run`). Tracked in
  #52.
- `lxml` (`6.1.1` available, currently resolves to `5.4.0`) — `linkedin-api==2.2.1` requires
  `lxml<6.0.0,>=5.3.0`; `pip install lxml==6.1.1 linkedin-api==2.2.1` fails with
  `ResolutionImpossible: linkedin-api 2.2.1 depends on lxml<6.0.0 and >=5.3.0`. `linkedin-api`
  is hard-pinned per policy, so `lxml` stays on the newest `linkedin-api`-compatible release.
  Related to #53.

## [1.7.0] - 2026-07-26

### Added
- **DB-backed, versioned profile + admin JSON upload.** The scraper's
  `profile_data.json` can now be uploaded from the admin **Profile Data** page and is stored
  **versioned, per language** (EN/DE evolve independently — one active version each).
  - Backend: `ProfileSnapshot` model (table `profile_snapshots`, unique `(version, language)`),
    public `GET /api/app/profile?lang=en|de` (active snapshot; 404 → frontend falls back to the
    bundled static asset), admin `POST /admin/profile/upload`, `GET /admin/profile/versions`,
    `PATCH /admin/profile/versions/{id}/activate`. Alembic migration `a1b2c3d4e5f6`.
  - **Security**: the public endpoint serves a **field allowlist**, never the raw stored blob, so an
    uploaded scraper JSON can't leak non-public PII (phone/address/connections); `contact` is
    reduced to email+linkedin. Admin upload is **size-capped** (413), `sort_by` is allowlisted, and
    full auth coverage (401 unauth / 403 non-admin) is enforced and tested.
  - Public site now loads the profile from the backend (with a static-asset fallback), so an
    upload is reflected immediately. Site-enriched fields (`contact`, `recommendations`,
    `certifications`, `languages`) are optional and every block guards for absence, so a raw
    scraper `profile_data.json` renders cleanly even when it omits them.
- **Bulk posts import from `posts_data.json`.** `POST /api/app/linkedin/import-posts-json` and an
  **Upload posts_data.json** button in the admin LinkedIn tab upsert scraper posts by URN as drafts
  (idempotent). Images are downloaded best-effort from LinkedIn's CDN, else the remote URL is kept.
  - Security-hardened: image fetch is restricted to https `*.licdn.com` (SSRF guard; the `li_at`
    cookie never leaves LinkedIn), redirects are not followed, and the upload/post-count/image size
    are bounded (413 over limit).

### Notes
- Full test coverage: backend 100% (new `profile`/`admin_profile`/`linkedin` paths), admin app 100%
  (service + Profile Data component + posts-JSON upload) and public app 100%, plus **admin-e2e**
  (Profile Data page) and **public-e2e** (backend profile render + minimal-JSON resilience).

## [1.6.0] - 2026-07-25

### Changed
- **Angular 21 → 22 major upgrade** across the whole workspace (`shared` / `public` / `admin`).
  All `@angular/*` packages, `@angular/build`, `@angular/cli`, `ng-packagr` moved to `22.x`;
  TypeScript bumped to `~6.0` and `@types/node` to `22.x` to satisfy Angular 22's peer ranges.
  Triggered by a Dependabot partial bump of `@angular/build` to v22 against a v21 framework, which
  broke the build; resolved by completing the full major migration rather than pinning back.
- **HttpClient Fetch backend** — Angular 22 defaults `HttpClient` to the Fetch backend; the public
  blog specs were adjusted to target the posts request explicitly so the change in transport no
  longer confuses the native-`fetch` infinite-scroll assertions (no runtime behavior change).

### Added
- **Dependabot configuration** (`.github/dependabot.yml`) — replaces the empty placeholder. The
  Angular toolchain is now **grouped into a single PR** and **major bumps are ignored** for
  `@angular/*`, `@angular/build`, `ng-packagr`, and `typescript`, so the workspace can never again
  be left with a half-migrated major. Also covers backend pip (linkedin-api pinned/ignored),
  GitHub Actions, and Docker base images with grouped weekly updates.

## [1.5.2] - 2026-07-25

### Changed
- **Clearer CI job names** in `deploy.yml` — per-app frontend lanes and E2E steps renamed to a
  consistent scheme (`Frontend Tests · Shared Library` / `· Public App (SSR)` / `· Admin App (SPA)`;
  `Build Public Frontend Image`; `E2E · Public Site` / `E2E · Admin Console`).
- **Behavior docs** — `CLAUDE.md`, the `backend-dev` / `frontend-dev` / `devops-pipeline` subagents,
  and the `/release` runbook updated to the PR-based workflow (never push feature work to `main`
  directly), the full local test round (backend + frontend + E2E), and a per-release security-report
  check; agent paths updated for the frontend workspace split.

## [1.5.1] - 2026-07-25

### Changed
- **CI flow split per app** — `deploy.yml` now runs one test lane per workspace project
  (`frontend-shared-tests` / `frontend-public-tests` / `frontend-admin-tests`, distinct
  Codecov flags); each image build depends on its own lane; the E2E job runs two explicit
  steps, `E2E — Public (public-e2e)` and `E2E — Admin (admin-e2e)`, so the public and admin
  flows are legible end to end.

### Added
- **Pre-push test gate** (`.claude/hooks/pre-push-tests.sh`, wired via `.claude/settings.json`)
  — before any `git push`, runs a docs check (CHANGELOG `[Unreleased]` + README), the backend
  pytest suite, and the frontend shared/public/admin unit tests, blocking the push on failure.
  Self-gates on the push command so it never interferes with other shell commands; all legs are
  env-configurable (`PREPUSH_RUN_BACKEND` / `PREPUSH_RUN_FRONTEND` / `PREPUSH_CHECK_DOCS` /
  `TEST_DATABASE_URL`).

### Fixed
- Hardened the cross-app blog E2E specs to wait for admin logout to settle before the
  cross-origin navigation to the public site.

## [1.5.0] - 2026-07-25

### Added
- **Frontend split into two independent apps.** The single Angular app is now an Angular
  workspace with three projects under `frontend/projects/`:
  - `public` — the SSR visitor site (home, blog, cv, llm, marketing shell), unauthenticated.
  - `admin` — a CSR-only admin console SPA (login + management), served on the restricted
    `admin.mavrov.de` subdomain.
  - `@mavrov/shared` — an ng-packagr library holding the code both apps share (blog/stats/llm/
    language/storage services, translate pipe, i18n), decoupled from the host app via the
    `SHARED_ENVIRONMENT` and `AUTH_TOKEN_PROVIDER` injection tokens.
  Each app builds, tests (100% coverage per project), and deploys independently.
- **Second frontend Docker image** `…-admin-frontend` (static nginx SPA, no SSR/Node) plus a
  dedicated `admin.mavrov.de` reverse-proxy server block with a loopback-allowed access
  allowlist (`proxy/admin_allowlist.conf`) and `noindex` headers.

### Changed
- CI (`deploy.yml`) now builds/tests/publishes both frontends and runs the Playwright E2E suite
  split into `public-e2e` and `admin-e2e` projects. `release.sh` / `build_amd64_and_push.sh`
  build and promote the admin image alongside the others.

## [1.4.2] - 2026-07-25

### Added
- **Ollama model prewarming** — the `ollama` service now loads the generation models
  (`llama3.2`, `llama3.2:1b`) into memory right after pulling them, and keeps all models
  resident (`OLLAMA_KEEP_ALIVE=-1`, prod `OLLAMA_MAX_LOADED_MODELS` raised to 3), so the first
  chat/tag request is not a multi-second cold start.

### Changed
- **Timeline reaches the present** — `GET /api/app/cv/years` now always includes the current
  calendar year, so the header year-slider shows the current year (e.g. 2026) even when no
  experience *started* this year.
- `/release` slash command now mirrors `release.sh` end-to-end (all steps documented).

### Fixed
- **Prod pulled stale images** — `docker-compose.prod.yml` image tags were pinned to the previous
  release's default (`IMAGE_TAG:-1.4.0`); `bump_version.sh` never updated them (only `release.sh`
  does). Bumped to the current version so the prod server pulls the right images.
- **Ollama models re-downloaded on every restart** — `ollama pull` is now guarded by an
  `ollama list` check, so models already in the persistent `ollama_data` volume are not
  re-downloaded (offline-safe once cached).
- **`HeaderComponent` NG0100** — subscribe to `YearsService.getYears()` in the constructor rather
  than `ngOnInit`, so a synchronous `shareReplay(1)` replay can't mutate bindings after the view
  was checked (removes the dev-mode `ExpressionChangedAfterItHasBeenCheckedError`).

## [1.4.1] - 2026-07-25

### Changed
- **Dependency modernization** to latest **within current majors** (deliberately not crossing
  breaking majors — no Angular 22, TypeScript 7, or google-genai 2):
  - Backend: `fastapi` 0.129→0.140, `sqlalchemy` 2.0.46→2.0.51, `pgvector` 0.4.2→0.5.0,
    `alembic` 1.18.4→1.18.5, `uvicorn` 0.41→0.51, `Pillow` 12.2→12.3, `python-multipart`
    0.0.26→0.0.32, `google-genai` 1.64→1.75, `setuptools` 69.5→83, `respx` 0.22→0.23.1.
    (`linkedin-api` stays 2.2.1 — prod installs a patched wheel.)
  - Frontend: Angular 21.2.17→21.2.19, `tailwindcss` 4.0→4.3, `vitest` 4.1.9→4.1.10,
    `express` 5.1→5.2, `zone.js` 0.16.0→0.16.2, `@playwright/test` 1.58→1.62,
    `@analogjs/vite-plugin-angular` 2.2→2.6.4 (TypeScript pinned at 5.9.x, `@types/node` at 20.x).
- **CrewAI 0.11.0 → 1.15.6** (Python 3.13 compatible). `multi_chat.py` migrated off the
  removed `langchain.tools` to `langchain_core.tools`; `langchain-openai` 0.0.2→1.4.1;
  `ChatOpenAI` `api_key` typed as `SecretStr` for the stricter 1.x signatures.
- **Chat agents**: `fast_generation_model` switched `tinyllama` → `llama3.2:1b` (cleaner,
  parseable JSON for tag/metadata generation at a similar footprint). Compose `ollama pull`
  lists and healthchecks updated to match.

### Added
- Scraper: both `scrape-linkedin.js` (profile) and `scrape-posts.js` (posts) now reuse a
  single persistent Chrome profile session, and honor `PLAYWRIGHT_CHANNEL` (e.g. `chrome`) to
  drive system Google Chrome instead of the bundled Chromium.
- Production backend accepts `LINKEDIN_IMPORT_TOKEN` and `IMPORT_MAX_IMAGE_MB` env vars,
  enabling authenticated LinkedIn post import against production.

## [1.4.0] - 2026-07-08

### Added
- **LinkedIn post import (end-to-end)** — move LinkedIn posts (text **and** images) into the
  mavrov.de blog:
  - `POST /api/app/linkedin/import-post` — multipart ingest of one post (text + optional image
    bytes). Stores the image **locally** (served from our own domain via
    `GET /api/app/posts/{id}/image`) and **upserts by LinkedIn URN** so re-imports never
    duplicate. Auth by `X-Import-Token` (constant-time compare) **or** an admin JWT; image type
    allowlist (`415`) + size cap `import_max_image_mb` (`413`); tags derived from hashtags.
    Imported posts are drafts by default. (spec 04)
  - `Post` provenance columns `source_urn` (partial-unique when not null), `source_url`,
    `posted_at`, with Alembic migration `c3f8a1d2e947`. (spec 01)
  - Import settings `linkedin_import_token` and `import_max_image_mb`. (spec 02)
  - LinkedIn text normalization helpers `normalize_linkedin_text` / `extract_hashtags` (strip the
    literal `hashtag` labels + zero-width chars; hashtags → tags). (spec 03)
- **Scraper** — correct post image/date extraction: captures the post's **own** media (no longer
  the author's profile photo), decodes `postedAt` from the activity URN's embedded timestamp,
  emits a stable `posts_data.json` schema, adds `scrape:posts` / `scrape:posts:debug` / `test`
  npm scripts, gentle scraping (session reuse, randomized delays, `SCRAPE_MAX_POSTS`), and a pure
  `parse-post.js` unit-tested with `node --test`. (spec 05)
- **Standalone importer** (`importer/`, independent of the A2A team) — drives the scraper,
  downloads each image with the LinkedIn session, and posts to the ingest endpoint. Idempotent
  (server URN upsert + local processed-URN ledger), retry/backoff (one bad post never aborts the
  batch), oldest→newest, `--dry-run` / `--watch` / `--publish`; 10 pytest tests (mocked HTTP). (spec 06)
- Decomposed feature-spec workflow under `specs/planned/` (run order + `_full-reference.md`).

### Changed
- A2A agent team now defaults to **Claude** (`claude-sonnet-4-6`) with **prompt caching** on the
  system prompt + tool definitions + a rolling tool-transcript breakpoint; `A2A_LOG_USAGE=1`
  surfaces per-call cache hits.
- Autonomous pipeline hardened from live-run experience: dev agents **implement via tools**
  (rather than only describing a plan); the deterministic gate now **mirrors CI** (auto
  `ruff format` + `ruff check --fix` + `mypy` before pytest); an empty implement is treated as a
  **RED** gate (no fake-green); the PR title is derived from the spec's H1 and length-capped;
  `run_tests` uses the checkout's venv; each agent server waits for its port to free (fixes the
  recurring `:8021` bind race).

### Fixed
- Backend coverage traces greenlets (`concurrency = ["thread", "greenlet"]`) so lines executed
  after SQLAlchemy-async awaits are recorded — async DB endpoints no longer mis-report as
  uncovered.
- Ruff-formatted autonomous LinkedIn changes that had reached `main` unformatted.

## [1.3.0] - 2026-07-06

### Added
- A2A multi-agent delivery team (12 roles: PM, architect, story-writer, backend/frontend dev, QA, code-reviewer, LinkedIn checker, DevOps, security-reviewer, documentation-writer, release-manager) as real Agent2Agent servers (Agent Cards + JSON-RPC) with a PM orchestrator, an inter-agent dependency graph, Docker compose and 25 tests, under `agents/`.
- Pluggable LLM brain for the agents: Ollama-first (local, no API key) with Gemini/Anthropic/stub fallbacks; recommended model qwen2.5-coder:7b.

## [1.2.29] - 2026-07-06

### Added
- Project MCP servers for Claude Code (`postgres`, `playwright`, `github`).
- CI-fix agent team under `.claude/agents/` (`devops-pipeline`, `backend-dev`, `frontend-dev`).
- Dependabot configuration.

### Security
- Dependency remediation: bumped `pillow`, `pydantic-settings`, `python-dotenv`, `python-multipart`, `pytest`; resolved npm advisories via `npm audit fix` + Angular 21.x patch bumps (`undici`, `vite`, `hono`, `path-to-regexp`, `postcss`, `esbuild`, ...). Open Dependabot alerts reduced from 85 to 3 low-severity (deferred -- require a breaking Angular 22 upgrade).
- Dismissed the `py/sql-injection` CodeQL alert on the admin SQL console as accepted risk (admin-gated; arbitrary SQL is the feature's intent).
- Dismissed `setuptools` and `langchain-openai` advisories as tolerable risk (CrewAI `pkg_resources` compatibility pin; breaking major bump avoided).

### Fixed
- Restored server-side rendering behind the reverse proxy: Angular 21.2's `@angular/ssr` SSRF host allowlist was silently falling back to client-side rendering. Fixed with `NG_ALLOWED_HOSTS` + `trustProxyHeaders: true` (title, `<h1>`, and content now present in initial SSR HTML).
- Resolved CI lint/format failures (`ruff` F401 + formatting) introduced by the new coverage suites.

### Changed
- Excluded the SSR server entry (`src/server.ts`) from coverage, consistent with `src/main.ts`; frontend coverage remains 100%.

## [1.2.28] - 2026-07-05

### Added
- 100% line & branch coverage -- backend (605 tests) and frontend (687 tests).
- Merged still-compatible test and scraper additions salvaged from a pre-rebase branch.

### Changed
- Ignored the scraper Chrome profile and browser runtime artifacts.

## [1.2.27] - 2026-03-15

## [1.2.26] - 2026-03-15

### Fixed
- Fixed SQL injection vulnerability in `execute_sql` in admin API.
- Fixed information exposure through exception stack traces in AI API.

## [1.2.25] - 2026-03-15

### Added
- Standardized AI Assistant global prompt configurations across all major cloud/desktop tools (`.cursorrules`, `.windsurfrules`, `.cline.md`, `AI.md`, etc.).
- Embedded ultra-strict "Mission Command" directives for clean code, solid principles, and zero-tolerance bug resolutions.

### Changed
- Increased Docker Compose healthcheck retries for the Ollama container from 60 to 180 (10 mins to 30 mins) to prevent initialization timeouts during model downloads in CI.

- Implemented `ssr.interceptor.ts` in Angular to properly route relative API calls during SSR (Server-Side Rendering) by correctly resolving `http://backend:8000` via the internal Docker DNS.
- Extended unit tests in Frontend to achieve 100% coverage on `blog-post.component.ts` and intercepted logic.
- Extended unit tests in Backend `app/api/posts.py` to achieve full coverage on draft permissions, image uploading logic, and retry generation cases.
- E2E Testing configuration adjusted to run Playwright tests against proper `BASE_URL` target inside local Docker environment.

- Improved fallback SEO metadata handling in the blog component in case the post summary is missing.
- Reorganized `APP_CONFIG` interceptors to include SSR functionality implicitly without manual code workarounds.

### Security

- **CRITICAL**: Removed `NODE_TLS_REJECT_UNAUTHORIZED=0` parameter from the `frontend` container in `docker-compose.prod.yml`. The application no longer overrides Node TLS certificate validation checks; the SSR Interceptor properly avoids self-signed SSL certificate issues by rendering data directly from the unencrypted Docker DNS internal network (`http://backend:8000`).

### Fixed

- Fixed bug where blog posts were returning `302 Found` Redirects or `404 Not Found` when directly opening their URLs due to relative pathing issues during Express server-side rendering.
- Fixed `window.location` references resolving incorrectly in the Vitest frontend suite.
