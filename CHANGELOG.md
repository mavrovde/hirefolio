# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Placeholder for next release.

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
