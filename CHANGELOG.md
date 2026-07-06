# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Import configuration settings** (`linkedin_import_token`, `import_max_image_mb`): two new
  `Settings` fields in `backend/app/config.py` that the upcoming LinkedIn import endpoint will
  consume. `linkedin_import_token` (default `""`) is the machine auth token for the import
  endpoint — an empty value means the endpoint is disabled. `import_max_image_mb` (default `10`)
  caps the image size accepted by the import endpoint. Both fields follow the existing
  `linkedin_*` style, are overridable via environment variables (pydantic-settings), and are
  covered by a dedicated test in `backend/tests/test_config.py`. No endpoint or auth logic is
  added in this change.
- **LinkedIn provenance columns on `Post`** (`source_urn`, `source_url`, `posted_at`): three
  nullable columns that enable idempotent LinkedIn imports. `source_urn` carries a partial unique
  index (`WHERE source_urn IS NOT NULL`) so two NULL values are allowed but two identical non-null
  URNs are rejected. `source_url` stores the LinkedIn permalink (max 512 chars) and `posted_at`
  stores the original publish timestamp with timezone. All existing rows receive NULLs; no
  endpoint or API response shape is changed.
- Alembic migration `c3f8a1d2e947` (revises `d45b3e9ce716`) adds the three columns and the
  partial unique index with a matching `downgrade()` that drops them cleanly.
- Three focused model tests: nullable defaults, duplicate-URN integrity error, and two-NULL
  coexistence.

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
