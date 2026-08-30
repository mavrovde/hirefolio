---
name: lessons-learned
description: >-
  The committed "do-not-repeat" knowledge base for mavrov.de — hard-won operational lessons
  and footguns that unit tests and PR CI do NOT catch. Consult BEFORE touching the frontend
  SSR/HTTP/change-detection path, running backend pytest locally, adding a GitHub Actions
  cache, deciding a release SemVer bump, running destructive local/infra commands, writing any
  test or CI job that touches an external service, or shipping a release. Encodes the zoneless-CD +
  SSR-HttpBackend traps, pytest local-DB isolation, the GHA multi-GB-cache net-negative,
  SemVer-by-content, the green-pipeline release rule, the no-irreversible-local-destruction
  guardrail, the STRICT no-real-API-keys/paid-credentials-in-tests-or-CI rule, and the mandatory
  independent-review-gate-before-merge rule, the bisect-gate-failures-against-a-clean-main-build
  triage method, and the @angular/* exact-peer single-pass-update/lockfile-regeneration rule.
  Grep it or load it when a task matches — it exists so
  fresh contexts and teammates don't re-research answers we already have.
---

# Lessons learned — mavrov.de (do not repeat)

This is the **in-repo** home for durable, hard-won lessons — the things that cost us a revert, a red
pipeline, or a wasted research loop. It complements `CLAUDE.md` (the rules) with the *why* and the
concrete reproduction. **Sync discipline:** when you learn a new durable lesson, add it here as part
of the change — do not leave it only in a machine-local private memory, or it evaporates between
contexts and contributors.

Each entry: **the trap → why it bites → how to apply.** Most of these are invisible to unit tests and
PR CI (which runs only CodeQL) — they only surface in the full Docker E2E or in production.

---

## 1. The public app is effectively ZONELESS — async property mutations don't repaint

**Trap.** `frontend/projects/public` bundles **no `zone.js`** at runtime (`angular.json` has no
`polyfills` entry; zone.js is only in `test-setup.ts` for unit tests). A component that mutates a
**plain property** inside a `subscribe` / `setInterval` / `setTimeout` / `async`-`fetch` callback will
**silently never repaint**. This froze the footer at `BE: vUnknown` / `UPTIME 00:00:00` (#94) even
though the `/stats/public` fetch returned 200.

**Why it bites.** Unit tests DO bundle zone.js, so change detection fires there and the test passes —
the freeze only appears in the browser / Docker E2E.

**How to apply.** For any public component that updates on a timer or a `subscribe`, repaint
explicitly: inject `ChangeDetectorRef` and call `markForCheck()` after each async mutation, **or** use
signals, **or** render an `Observable` via the `async` pipe. The app is committed to zoneless via
`provideZonelessChangeDetection()` in `app.config.ts` (#105) — the async-mutation rule still holds.
Grep pattern to audit: `subscribe(` / `setInterval(` / `setTimeout(` in `projects/public` that assign
`this.<prop> =` without a following `markForCheck()`.

## 2. SSR relative→absolute URL rewrite belongs in an `HttpBackend`, delegating to `HttpXhrBackend`

**Trap.** Doing the SSR URL rewrite in an `HttpInterceptorFn` runs it *before* Angular's
transfer-cache interceptor, so the server keys the transfer cache on the *rewritten* absolute URL
while the browser keys it on the *relative* URL → keys never match → the browser re-fetches every
request on hydration (blog `/blog/:slug` "flash to home", #25).

**Why it bites — and the specific landmine.** Fix by doing the rewrite in a custom `HttpBackend`
(terminal in the chain, runs *after* transfer-cache keying): `interceptors/ssr-http-backend.ts`
(`SsrHttpBackend`), wired via `provideHttpClient()` + `{provide: HttpBackend, useClass: SsrHttpBackend}`.
**CRITICAL: delegate to `HttpXhrBackend`, NOT `FetchBackend`.** The app has always used XHR on both
platforms. The reverted #84 delegated to `FetchBackend` and *deterministically* broke the browser's
`GET /api/app/stats/public` (`net::ERR_FAILED`), blocking the deploy across 4 attempts; only reverting
greened it. `HttpXhrBackend` keeps the browser byte-identical to the baseline.

**How to apply.** Never force the browser onto a different HTTP backend without proving it in the E2E.

## 3. SSR / HTTP / transfer-cache changes MUST be E2E-validated before merge

**Trap.** PR CI here runs **only CodeQL** — the real test suite + Docker E2E run in `deploy.yml` on
push to `main`. A browser-only regression sails through PR review and 100% unit coverage and only
surfaces *post-merge* on the prod deploy.

**How to apply.** For any change touching `HttpBackend` / `provideHttpClient` / interceptors /
transfer-cache / SSR hydration, run the full Docker E2E locally (`./verify_all.sh` or a targeted stack
repro) **before** merging. `frontend-dev` and `pr-reviewer` should explicitly ask "was this
E2E-validated?" for such changes. When you change a user-visible behavior, grep **all** e2e specs for
the OLD assertion (the #108→#110 stale-test fix-forward). Fix-forward on red: revert the offending
change to ship the rest, then redo it properly (never leave `main` red).

## 4. Backend pytest local DB — isolation rules (or it hangs / wipes the dev DB)

- **Always** export `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/test_mavrov`
  and `GEMINI_API_KEY=""` before `./venv/bin/pytest`. This is exactly what
  `.claude/hooks/pre-push-tests.sh` sets. Without it, `conftest.get_test_engine()` falls back to the
  **live `mavrov` dev DB**, and the per-test `Base.metadata.drop_all` **hangs** on the running backend
  container's table locks (and would wipe the dev DB if it didn't block).
- The `test_mavrov` DB lives in the `mavrovde-db-1` container. Create if missing:
  `docker exec mavrovde-db-1 psql -U postgres -p 5433 -c "CREATE DATABASE test_mavrov"`.
- **Never run two full pytest suites against `test_mavrov` at once** (e.g. a manual run while the
  pre-push hook fires). Both do `drop_all`/`create_all` per test on the same DB and clobber each other
  → dozens of spurious `InvalidRequestError: Could not refresh instance` / count-mismatch failures.
  Serialize them.
- `pyproject.toml` addopts already do `--cov=app`. Passing **extra** `--cov=app.api.foo` on the CLI can
  **segfault** (coverage C-tracer + asyncpg/greenlet). Use the plain full-suite run for the real
  coverage number; `--no-cov` for quick pass/fail iteration. Full suite ≈ 2.5 min; `pytest -q | tail`
  buffers until exit — use `-v` or write to a file for live progress.

## 5. GitHub Actions cache for multi-GB Docker artifacts is usually net-NEGATIVE

**Trap.** Caching large (multi-GB) base images or model weights via `actions/cache` does **not** speed
this pipeline up — the cache *transfer* (download tarball + `docker load`/extract) costs about as much
as re-pulling from the registry, and it eats the repo's 10 GB cache budget.

**Measured (v1.8.0 cycle).** #78 Ollama model-weights cache (~3.6 GB): +53s restore vs ~11s saved →
E2E job ~56s **slower**. #72/#76 base-image cache (~2.79 GB): ~30s saving at best (~2% of a 25-min
pipeline). The real bottleneck is the **sequential critical path**, not downloads: Backend Tests ~5m →
Build Backend Image ~5m → E2E ~8–9m → Proxy Verify ~5m. Real levers (issue #91): dedupe the two stack
bring-ups, `pytest-xdist -n auto`, and slim the backend image (done in #91 — dropping unused Node.js +
Playwright + Chromium cut ~500MB and the dominant build step).

**How to apply.** Before adding an `actions/cache` for a big Docker blob, estimate transfer vs
re-pull; prefer registry (CDN-backed) pulls. **Always MEASURE** before/after on real runs
(`gh api .../jobs` timings) — never assume a cache helps.

A corollary found in #134: **a cache placed downstream of its consumer is dead weight** — the E2E
job restored a multi-GB base-image cache *after* `docker compose up -d` had already pulled every
image, so it never saved a pull and cost 2 min per run (10 min on a miss). Audit step *ordering*,
not just hit rate.

## 6. Release SemVer bump is decided BY CONTENT of `[Unreleased]` — never by reflex

Stop at the first that matches:
- **MAJOR `X.0.0`** — any backward-**incompatible** change (removed/renamed API field or endpoint,
  non-additive DB migration, changed default/auth/config-key meaning). Signal: `feat!:` / `BREAKING
  CHANGE:`. Rare; confirm first.
- **MINOR `x.Y.0`** — ONLY if `[Unreleased]` has an `### Added` describing genuinely new,
  backward-compatible functionality (new endpoint/page/capability/feature-flag). Signal: `feat:`.
- **PATCH `x.y.Z`** (the maintenance default) — everything else: dependency bumps (even many at once),
  `### Fixed`, perf, refactors, internal tooling/CI, docs, additive-only migrations. Signals:
  `fix:`/`chore:`/`refactor:`/`perf:`/`docs:`/`ci:`.

**Rule of thumb:** only `### Changed`/`### Fixed`, no `### Added` feature → **patch**. Internal
AI-config/tooling/docs changes are patch-level (do not file them under `### Added`, which would
mislead the bump). Calibration: deps-only sweeps = patch (once wrongly defaulted to a minor — corrected).

## 7. A release is confirmed only when `deploy.yml` is GREEN end-to-end

Publishing is gated behind E2E/smoke, so a red pipeline ships nothing. After merging to `main`,
actively babysit the run (`gh run view <id> --json ... jobs`), surface each job result, and fix root
causes on red (fix-forward, never silent rollback). Only then tag `vX.Y.Z` (a tag push does not
re-trigger the branch pipeline). **Check GitHub security reports every release** — CodeQL
(`gh api .../code-scanning/alerts`) + Dependabot (`.../dependabot/alerts`) — triage each and note
pre-existing vs introduced. Caveat: a green publish updates the host only when the secrets-gated
`deploy` rollout job ran (#175); with `DEPLOY_*` unset it skips and the run is still green
("published ≠ live", #112) — check the job's status rather than assuming.

## 8. No irreversible LOCAL/infra destruction without explicit authorization

Never `docker volume rm`/`prune`, `docker compose down -v`/`--volumes`, `docker system prune`,
`docker image prune -a`, DROP/recreate a **non-`test_*`** database, or `rm -rf` a data dir / volume
mount **without explicit user authorization naming the resource** — a backup is **not** consent. Only
`test_*` DBs may be dropped autonomously. Origin: the #91 incident where a subagent ran
`docker volume rm mavrovde_open-webui_data` on its own initiative. Enforced by CLAUDE.md **rule 9** and
the `.claude/hooks/guard-destructive.sh` PreToolUse hook (bypass one authorized command with
`GUARD_DESTRUCTIVE=0` prefixed). Prefer non-destructive paths (bump the image to match the volume
schema, migrate, or leave it); if a workaround needs destroying local state, STOP and ask.

## 9. Deliver via PR; run the FULL suite before pushing; merge only when green

Never push feature work directly to `main` — branch → PR → merge (the merge is the sanctioned prod
trigger). Before pushing run the full local round (backend ruff/format + mypy + pytest **and** all
frontend project tests **and**, for SSR/HTTP/E2E-affecting changes, the Docker E2E). The shared
pre-push hook (`.claude/hooks/pre-push-tests.sh`) enforces docs + backend + frontend and self-gates
(only fires on `git push`). When all gates are green and there is no explicit hold order, merge/deploy
without stopping to ask.

## 10. NEVER use real API keys / paid credentials in tests or CI (strictly forbidden)

**Trap.** A real credential for a paid, metered, or rate-limited service (any LLM/API that bills or
burns quota per call) wired into an automated test or a CI test stack fires on **every pipeline run** —
producing silent, unbounded, recurring cost and quota exhaustion, and exposing the credential to CI
logs. It hides easily: one test spec left unmocked, or a workflow injecting `${{ secrets.* }}` into a
test job's env "so the feature works", turns green CI into a money leak.

**How to apply (both layers).**
1. **Mock** the paid call at the test boundary — `page.route` in Playwright, monkeypatch/fake in
   pytest — so the request never leaves the test.
2. **Deny the credential** to every test/CI job: inject an **empty/dummy** key so the code path takes
   a **free local fallback** (e.g. Ollama here) instead of the paid API. In CI, pass `KEY: ""`, never
   `${{ secrets.* }}`. Real credentials belong **only** to the production runtime environment.
Before writing or running any test/CI path, verify it cannot reach a paid service with a live
credential. In review, treat a real paid-service secret in a test stack — or an unmocked paid-API
test — as a **blocker**. In this repo: `deploy.yml` passes `GEMINI_API_KEY: ""` to the E2E stack (→
Ollama fallback) and the admin AI-suggestion specs mock `/posts/suggest-*`. This is **CLAUDE.md
rule 10**.

## 11. Every PR needs an INDEPENDENT pr-reviewer verdict before merge — no exceptions

**Trap.** Under time pressure it is tempting to merge on "green CI", "a dev agent (backend-dev/
frontend-dev) already validated it", "it's a trivial one-line CI/docs change", or "the user was
directing it in real time". **None of those is an independent review.** Merging without a posted
`pr-reviewer` verdict skips the two-party gate, leaves no audit trail, and lets plausible-but-wrong
changes through — exactly the class the reviewer exists to catch.

**How to apply.** A PR is mergeable only when **all gates are green AND a `pr-reviewer` APPROVE verdict
is posted to the PR**. This holds for EVERY PR with no carve-outs — hotfixes/emergencies, dependency
bumps, trivial/CI/docs changes, and user-directed changes. Urgent → the review is **expedited, not
skipped**. The implementing dev agent delivers the PR and does **not** merge; its own passing suite is
necessary but not sufficient. Every merged PR must carry a visible review comment. If one ever slips
through un-reviewed, post a **retrospective** review on the merged PR and fix-forward on any finding
(as was done for the four un-gated merges in the incident that produced this rule). This is **CLAUDE.md
rule 11**, enforced via the `pr-reviewer` agent.

---

## 12. Admin IP allowlist is meaningless without `real_ip` — and don't gate startup on the FULL `nginx -t`

**Trap.** In the containerized prod topology the admin subdomain sits behind a front proxy (1panel)
+ Docker NAT, so nginx sees the **Docker bridge gateway** as `$remote_addr` for *every* external
client. An `allow/deny` allowlist on `$remote_addr` therefore can't distinguish operators — and
flipping it to `deny all;` locks the owner out too (#86, split from #60, which is exactly why the
hardening was deferred once). The fix is nginx `real_ip`: `set_real_ip_from <trusted upstream CIDR>`
+ `real_ip_header X-Forwarded-For` + `real_ip_recursive on` (in the **http** context) so
`$remote_addr` becomes the real client IP *before* the allowlist runs. This only works if the front
proxy actually forwards the real client IP in that header and its egress falls inside the trusted
CIDR — **verify the proxy access logs show the real external IP**, not the gateway, before trusting
the allowlist. That runtime check can't be reproduced locally (needs the live front-proxy topology).

**Second trap (the one that bites at deploy time).** Don't add an entrypoint fail-safe that gates on
a **full-config** `nginx -t`. The rendered config's `proxy_pass http://backend:8000` upstreams
resolve **only inside the compose network**; a standalone `nginx -t` (or a startup DNS race) fails
with `host not found in upstream "backend"`, which has nothing to do with the allowlist. Under
`set -e` that can abort the entrypoint and **crash the proxy — taking the public site down too**, or
misattribute the failure and overwrite the allowlist. Validate **only your generated snippets, in
isolation**, with a throwaway minimal `nginx -t -c` config (an `http{}` including `real_ip.conf` + a
dummy `server{}` including `admin_allowlist.conf`), and keep the check non-aborting.

**How to apply.**
1. Generate `real_ip.conf` + `admin_allowlist.conf` at container start from env
   (`proxy/generate-admin-config.sh`: `TRUSTED_PROXY_CIDRS`, `REAL_IP_HEADER`, `ADMIN_ALLOWED_CIDRS`).
   **Validate every env entry against an IPv4/IPv6/CIDR regex** — an unvalidated value injects
   arbitrary nginx directives into the included file.
2. Ship **CLOSED**: empty `ADMIN_ALLOWED_CIDRS` → `deny all;` (loopback only), **never** a blanket
   `allow all;` as the default. Regex-valid ≠ nginx-valid (e.g. `999.999.999.999` passes `[0-9]{1,3}`
   but nginx rejects it) — so the isolated-`nginx -t` fail-safe reverts to the closed default and the
   real `exec nginx` still starts clean.
3. Give the owner a **break-glass** that never depends on their dynamic IP: loopback from on the box
   (`docker compose exec proxy wget … --header 'Host: admin.<domain>' https://127.0.0.1/`).
4. E2E hits `admin.localhost` through the bridge with **no** `X-Forwarded-For`, so `real_ip` can't
   recover a client — open the allowlist for the test run **only** via env
   (`docker-compose.e2e.yml` + `deploy.yml` set `ADMIN_ALLOWED_CIDRS=0.0.0.0/0`), never in the shipped
   default. Unit-test the generator deterministically (`proxy/test-generate-admin-config.sh`).

---

## 13. A failing local gate is NOT proof your change broke it — bisect against a clean `main` build first

**The trap (2026-08-29, the #170 dep sweep):** `./verify_all.sh` failed its proxy-route check
(`mavrov.de/admin/login` expected 200, got 404) right after the Angular/SSR bump — which
pattern-matches perfectly to "the SSR upgrade changed unmatched-route handling." It hadn't.
Building the frontend from an **unmodified `main` worktree with the committed lockfile**
(`git worktree add … main && npm ci && npm run build:public`, serve `dist/public/server/server.mjs`,
curl the route) reproduced the exact same 404: the check itself was stale, written before the
July-2026 admin/public workspace split when the admin SPA still lived at `/admin/*` inside the
public app.
1. Before root-causing a gate failure *inside your diff*, spend the ~5 minutes to reproduce it on
   a clean `main` build. If main fails too, you're fixing a latent gate bug, not your regression —
   different fix, different PR framing.
2. **Live prod behavior is NOT ground truth for a check while rollout is broken (#112):** the stale
   check "passed" against prod only because prod itself was running a months-stale pre-split image.
   A check validated only against a stale deployment validates nothing.
3. Local E2E details that cost time: the proxy's HTTPS is published on host port **10443**
   (`https://localhost:10443`, see `PROXY_SSL_PORT` in `verify_proxy_routes.py`) — plain
   `https://localhost/` curls give `000`. Express's default `Cannot GET /x` body = no Angular route
   matched, so `angularApp.handle()` returned null and Express fell through — that's the
   unmatched-route signature, not an nginx 404.

## 14. `@angular/*` framework packages pin EXACT peer versions — partial updates can never resolve

Angular publishes every framework package with exact-version peers (`@angular/forms@22.1.1` needs
`@angular/common@"22.1.1"`, not `^22.1.1`). Consequences (hit during #170):
1. `npm install @angular/common@^22.1.4 …` with only *some* of the packages → ERESOLVE, always:
   any **exact-peer framework package** left out (e.g. dev-dep `@angular/platform-browser-dynamic`)
   anchors the whole tree to the old exact version (tooling like `build`/`cli`/`ssr` uses ranged
   `^22.0.0` peers and doesn't anchor — but update it in the same pass anyway). Update **every**
   `@angular/*` dependency (deps AND devDeps, incl.
   `build`/`cli`/`ssr`/`compiler-cli`) in **one** resolver pass.
2. Even the all-at-once pass can fail when the *installed* tree anchors arborist. The reliable
   escape is regenerating from ranges: update `package.json`, then `rm -rf node_modules
   package-lock.json && npm install`. Expect a large lock diff — review it programmatically
   (registry hosts, unexpected majors, root-deps-vs-package.json identity), not line-by-line.
3. Framework and tooling move on separate patch trains (framework 22.1.4 vs build/cli/ssr 22.1.6
   the same day) — matching their patch numbers is wrong; matching each group internally is what
   must hold.

---

## 15. NEVER module-mock a dependency you assert against — and beware exceptions raised *inside* a streaming generator

**The trap (2026-08-30, #180):** `POST /ai/multi-chat` was broken in production for five weeks
while 778 backend tests stayed green. Two independent failures made that possible:

1. **Vacuous module mocks.** `conftest.py` did `sys.modules["crewai"] = MagicMock()` (and the whole
   `langchain_*` tree). A MagicMock accepts *any* constructor call, so `Agent(llm=<ChatOpenAI>)` —
   which real crewai 1.x rejects with a `ValidationError` — "passed" in every test. Mocking a whole
   module makes every assertion about that library meaningless. Mock at the **network boundary**
   (httpx/respx, `page.route`), not the library boundary; module-mock only a dependency that
   genuinely cannot be imported in tests, and never one whose behavior the code depends on.
2. **A raise inside a streaming endpoint is invisible to `response.ok`.** The exception fired
   *before* the async generator's first `yield`, i.e. after Starlette had already sent
   `http.response.start`. The client therefore saw **HTTP 200 + `Transfer-Encoding: chunked`**, then
   a mid-body connection close — not a 500. Frontend guards keyed on `response.ok` never tripped;
   the page just rendered "Connection Error". **In any streaming handler, do all setup that can fail
   inside a `try` and degrade into an error chunk on the stream**, because status codes are no
   longer available to you once the body has started.

Corollaries: an E2E that `page.route`-mocks the very endpoint it is named after proves nothing about
that endpoint (`multi-agent.spec.ts` mocked it); and when a library bump is "validated" by a suite
that mocks the library, the validation is vacuous — check what the tests actually exercise.

---

## Where the rules live (AI-config map)

- **`CLAUDE.md`** — the authoritative numbered rules (engineering rules 1–11, issue-tracking flow,
  execution protocol). This skill is the *why + reproduction* companion.
- **`.claude/agents/*.md`** + **`agents/common/roster.py`** (`PROJECT_PLAYBOOK`) — the agent charters;
  keep the two in sync (they restate overlapping lessons).
- **`.claude/skills/issue-workflow/`** — the issue/PR/milestone/label operational flow.
- **`.claude/hooks/`** — `pre-push-tests.sh` (test gate), `guard-destructive.sh` (destruction guard).
- **`.claude/commands/`** — `/verify`, `/release`, `/issue-triage`, `/linkedin-sync`.
