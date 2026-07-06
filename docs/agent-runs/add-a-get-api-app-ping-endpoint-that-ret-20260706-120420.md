# Autonomous run — Add a GET /api/app/ping endpoint that returns {"ping": "ok"}, with a test

- Started: 2026-07-06T12:04:20
- Branch: agent/add-a-get-api-app-ping-endpoint-that-ret


## 12:04:20 — Setup

Isolated worktree `/tmp/mavrov-wt-agent-add-a-get-api-app-ping-endpoint-that-ret` on branch `agent/add-a-get-api-app-ping-endpoint-that-ret`.


## 12:05:57 — Research (researcher)

I have everything I need. Here is the complete research synthesis:

---

## Research Findings: Add `GET /api/app/ping` → `{"ping": "ok"}`

### 1. Where the URL prefix comes from

**File:** `backend/app/config.py`, line `api_prefix: str = "/api/app"`

Every router is registered with `prefix=settings.api_prefix` in `main.py` (lines 219–228). So a router with its own prefix of `/ping` will yield the full path `/api/app/ping`.

---

### 2. Two valid implementation strategies

Both exist in the codebase as precedents; choose one:

#### Option A — Inline `@app.get` on the `app` object in `main.py`

This is exactly how the existing `health` endpoint works (lines 236–238 of `backend/app/main.py`):

```python
@app.get(f"{settings.api_prefix}/health")
async def health_check():
    return {"status": "healthy"}
```

`ping` is similarly trivial — no DB, no auth — so the same pattern applies.

#### Option B — Dedicated `APIRouter` in `backend/app/api/`

This is how every other endpoint is structured (e.g. `app/api/stats.py`, `app/api/auth.py`, `app/api/years.py`). The router declares its own prefix and is imported + registered in `main.py`.

**Recommendation: Option A** (inline on `app`) — it's the established pattern for tiny, infrastructure-level endpoints (`/health`, `/`). A new file + import + `include_router` call would be over-engineering for a single route.

---

### 3. Exact change needed in `main.py`

After line 238 (`return {"status": "healthy"}`), add:

```python
@app.get(f"{settings.api_prefix}/ping")
async def ping():
    return {"ping": "ok"}
```

No imports needed — `settings` is already imported at the top of `main.py`.

---

### 4. Where the test goes and what it must look like

**Existing precedent:** `backend/tests/test_main.py` already tests `/` and `/api/app/health` (lines 1–15). The `ping` test belongs in the same file:

```python
@pytest.mark.asyncio
async def test_ping(client: AsyncClient):
    """Test ping endpoint."""
    response = await client.get(f"{settings.api_prefix}/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "ok"}
```

**Test infrastructure facts (from `backend/conftest.py`):**
- `client` fixture: `AsyncClient` with `ASGITransport(app=app)`, base URL `http://test`, DB + auth overrides applied — but `/ping` needs **neither**, so `client` is fine.
- `@pytest.mark.asyncio` + `asyncio_mode = "auto"` (from `pyproject.toml`) — both the decorator and auto-mode are used in existing tests.
- Import `settings` from `app.config` (already in `test_main.py`) so the prefix is not hardcoded.

---

### 5. Coverage requirement

`pyproject.toml` has `--cov=app` and `--cov-report=term-missing` but **no `--cov-fail-under` threshold** (grep returned exit 1). However, the team rule is **100% coverage must be maintained**. The new handler is a single `return` statement — one test hitting the happy path covers it fully. No branches, no conditionals.

---

### 6. No proxy/routing changes needed

**File:** `proxy/` directory would only matter if a new URL *prefix* needed proxying. `/api/app/*` is already forwarded to the backend by the existing nginx/proxy config; no changes there.

---

### 7. CI check list

| Check | Impact |
|---|---|
| **ruff** | No new lint issues — simple one-liner return |
| **mypy** | Return type inferred as `dict[str, str]` — no annotation needed, matches `health_check` pattern |
| **bandit** | No security-sensitive code |
| **pytest + coverage** | New test covers the new line; 100% maintained |
| **vitest / E2E** | Not affected — purely backend |

---

### Summary

**Two files to touch, minimal edits:**

| File | Change |
|---|---|
| `backend/app/main.py` | Add 3 lines after `health_check` (the `@app.get` decorator + `async def ping` + `return`) |
| `backend/tests/test_main.py` | Add one `async def test_ping` test function (≈6 lines) |

No new files, no new imports, no schema changes, no router registration needed.


## 12:07:02 — Specification (spec-analyst)

I now have everything I need. All claims are verified against real file contents.

---

# Requirements & Acceptance Criteria — `GET /api/app/ping`

## What Was Actually Observed (Sources of Truth)

| Claim | Verified In | Observed Fact |
|---|---|---|
| API prefix is `/api/app` | `backend/app/config.py:11` | `api_prefix: str = "/api/app"` |
| `health` endpoint is the inline `@app.get` precedent | `backend/app/main.py:236` | `@app.get(f"{settings.api_prefix}/health")` |
| 10 routers registered with `prefix=settings.api_prefix` | `backend/app/main.py:219–228` | All via `app.include_router(…, prefix=settings.api_prefix)` |
| `/api/app/` already proxied by nginx | `proxy/default.conf:42–49` | `location /api/app/ { proxy_pass http://backend:8000/api/app/; }` |
| `test_main.py` has 2 tests, both follow the same pattern | `backend/tests/test_main.py:7,17` | `test_root_endpoint`, `test_health_check` — `AsyncClient`, `settings.api_prefix`, `@pytest.mark.asyncio` |
| `asyncio_mode = "auto"` AND `@pytest.mark.asyncio` are both used | `backend/pyproject.toml` + `test_main.py` | Both are present; new test must match this style |
| No `--cov-fail-under` in pyproject.toml | `backend/pyproject.toml` (grep exit=1) | Confirmed absent — 100% rule is team convention only |
| `client` fixture wraps `ASGITransport(app=app)`, no auth/DB needed for this route | `backend/conftest.py` | Fixture exists; `/ping` requires neither auth nor DB |

---

## Scope

### In Scope
1. A new `GET /api/app/ping` endpoint on the FastAPI `app` object in `backend/app/main.py`.
2. Response body exactly: `{"ping": "ok"}`, HTTP 200.
3. One new test function `test_ping` in `backend/tests/test_main.py`.
4. The new endpoint and test must keep all CI checks green: `ruff`, `mypy`, `bandit`, `pytest` at 100% coverage.

### Explicitly Out of Scope
- No new files (no new `APIRouter`, no new module under `backend/app/api/`).
- No imports added to `main.py` (`settings` already imported at line 21).
- No changes to `proxy/default.conf` — `/api/app/` is already forwarded to the backend (line 42–49); `/api/app/ping` is covered by that rule.
- No authentication, no database, no request body, no path/query parameters.
- No frontend changes (Angular, Vitest, E2E).
- No version bump, no CHANGELOG entry (this is an infrastructure utility endpoint, not a user-facing feature requiring a release).

---

## Affected Areas (Exact Files)

| File | Change Type | Nature of Change |
|---|---|---|
| `backend/app/main.py` | Edit (3 lines added after line 238) | New inline route handler `ping()` |
| `backend/tests/test_main.py` | Edit (≈7 lines appended) | New `test_ping` test function |

No other files are touched. The proxy config (`proxy/default.conf`) requires **zero changes** because `location /api/app/` (line 42) already routes `GET /api/app/ping` to the backend.

---

## Concrete Requirements

### REQ-1 — Endpoint existence and path
The FastAPI application MUST expose a route at the exact path `GET /api/app/ping`. The path MUST be constructed as `f"{settings.api_prefix}/ping"` (not hardcoded as a string literal), so it tracks the configured prefix automatically.

> **Why:** `settings.api_prefix` is the single source of truth for the prefix, as confirmed in `config.py:11` and used on `main.py:236` for the existing `/health` route.

### REQ-2 — Response contract
A successful `GET /api/app/ping` MUST return:
- HTTP status code **200**
- `Content-Type: application/json`
- Body exactly: `{"ping": "ok"}` — no additional keys, no variation

### REQ-3 — No side effects
The handler MUST NOT touch the database, call any external service, require authentication, or read request parameters. It is a pure static responder.

### REQ-4 — Implementation pattern
The handler MUST be implemented as an inline `@app.get` on the `app` object (same as `health_check` on `main.py:236–238`), NOT as a new `APIRouter`. The function MUST be `async def`.

> **Rationale:** All infrastructure-level single-purpose endpoints (`/`, `/api/app/health`) use this pattern. A dedicated router file would be over-engineering for one unconditional `return`.

### REQ-5 — Test coverage
A test `test_ping` MUST be added to `backend/tests/test_main.py`. It MUST:
- Be decorated with `@pytest.mark.asyncio` (matching lines 6 and 16 of the existing file)
- Accept a single `client: AsyncClient` fixture argument (existing conftest fixture — no DB or auth needed, but the fixture still provides them)
- Assert HTTP 200
- Assert `response.json() == {"ping": "ok"}` (exact equality, not subset)
- Use `settings.api_prefix` from `app.config` (already imported on `test_main.py:1`) to construct the path — no hardcoded string literals

### REQ-6 — CI gates must stay green
After the change, all of the following MUST pass without modification to thresholds or skip markers:
- `ruff` (lint)
- `mypy` (types — return type `dict[str, str]` is trivially inferred)
- `bandit` (security — no sensitive operations)
- `pytest --cov=app` (coverage — one happy-path test covers the single `return` line; `branch = true` in `pyproject.toml` is satisfied because there are no branches)

---

## Open Questions

| # | Question | Impact | Owner |
|---|---|---|---|
| OQ-1 | Should `GET /api/app/ping` also be added as a dedicated `location /api/app/ping` block in `proxy/default.conf` (e.g. for load-balancer health checks that hit nginx directly at `/ping`)? | Low — the existing `/api/app/` catch-all already covers it for application use. Only relevant if an external probe needs a shorter path like `/ping`. | Product / DevOps |
| OQ-2 | Should the response include a timestamp or service name (e.g. `{"ping": "ok", "service": "mavrov-api"}`) to make it useful as a liveness probe beyond a simple reachability check? | None to this ticket — spec says `{"ping": "ok"}`. A future enhancement only. | Product |
| OQ-3 | Should this endpoint be documented in OpenAPI/Swagger with a `tags=["infra"]` label, or intentionally left untagged like `health_check`? | Cosmetic only — no functional impact on behaviour or tests. | Product |

---

## Testable Acceptance Criteria

These are the direct gates for "done." Each is independently verifiable by a developer, reviewer, or CI run.

---

**AC-1 — Route is reachable and returns the contract**
```
GIVEN the backend application is running
WHEN  GET /api/app/ping is called with no headers, body, or auth
THEN  HTTP 200 is returned
AND   the response body is exactly {"ping": "ok"}
AND   Content-Type is application/json
```

**AC-2 — No authentication is required**
```
GIVEN a request with no Authorization header and no session cookie
WHEN  GET /api/app/ping is called
THEN  HTTP 200 is returned (not 401 or 403)
```

**AC-3 — Method restriction**
```
WHEN  POST /api/app/ping is called
THEN  HTTP 405 Method Not Allowed is returned
```
> *This is FastAPI's default behaviour for unregistered methods — no extra code needed, but it should be noted as observable.*

**AC-4 — Test exists and passes**
```
GIVEN the test suite at backend/tests/test_main.py
WHEN  pytest is executed
THEN  test_ping passes (assert 200, assert {"ping": "ok"})
AND   no existing test (test_root_endpoint, test_health_check) is broken
```

**AC-5 — Coverage is maintained**
```
WHEN  pytest --cov=app --cov-report=term-missing is run after the change
THEN  the new line(s) in main.py are shown as covered (not missing)
AND   overall coverage does not decrease from the pre-change baseline
```

**AC-6 — Lint and types pass**
```
WHEN  ruff check backend/app/main.py is run
THEN  exit code 0, no new violations

WHEN  mypy backend/app/main.py is run
THEN  exit code 0, no new type errors
```

**AC-7 — Proxy routing (observable without code change)**
```
GIVEN the full docker-compose stack is running
WHEN  GET https://mavrov.de/api/app/ping is called through nginx
THEN  nginx routes it to the backend via the existing /api/app/ location block
AND   HTTP 200 {"ping": "ok"} is returned end-to-end
```
> *No proxy config change is needed. This AC validates that the existing nginx rule covers the new path.*

---

## Implementation Checklist (for the developer)

- [ ] In `backend/app/main.py`, add after the `health_check` block (after line 238):
  ```python
  @app.get(f"{settings.api_prefix}/ping")
  async def ping():
      return {"ping": "ok"}
  ```
- [ ] In `backend/tests/test_main.py`, append:
  ```python
  @pytest.mark.asyncio
  async def test_ping(client: AsyncClient):
      """Test ping endpoint."""
      response = await client.get(f"{settings.api_prefix}/ping")
      assert response.status_code == 200
      assert response.json() == {"ping": "ok"}
  ```
- [ ] Run `pytest` locally and confirm all three tests in `test_main.py` pass and coverage is intact.
- [ ] Run `ruff check` and `mypy` locally — expect zero new issues.
- [ ] Commit with message: `feat(api): add GET /api/app/ping liveness endpoint` + body describing what and why.


## 12:07:52 — Plan (planner)

All facts confirmed. Here is the complete, grounded implementation plan.

---

## Implementation Plan — `GET /api/app/ping`

### Verified Ground Truth

| Fact | Source | Value |
|---|---|---|
| API prefix constant | `backend/app/config.py:11` | `api_prefix: str = "/api/app"` |
| `settings` already imported in `main.py` | `backend/app/main.py:21` | `from app.config import settings` |
| Inline route precedent | `main.py:236–238` | `@app.get(f"{settings.api_prefix}/health")` / `async def health_check()` |
| Test file imports | `backend/tests/test_main.py:1–3` | `from app.config import settings`, `pytest`, `AsyncClient` — all needed imports already present |
| Test decoration pattern | `test_main.py:5,15` | `@pytest.mark.asyncio` on every test |
| `asyncio_mode = "auto"` | `backend/pyproject.toml:7` | Present — but `@pytest.mark.asyncio` is still used on existing tests; new test must match their style |
| Branch coverage enabled | `backend/pyproject.toml:25` | `branch = true` — the new handler has zero branches, one `return`; single test covers it completely |
| No `--cov-fail-under` | `pyproject.toml` grep (exit 0, no match) | 100% is team convention enforced by reading output, not a CLI flag |
| `client` fixture | `backend/conftest.py` | `async def client(db_session)` — wraps `ASGITransport(app=app)`; no auth/DB needed for `/ping` but the fixture still provides them |
| Exact insertion point | `main.py:238` | Last line of `health_check` is `return {"status": "healthy"}` — new block goes immediately after |

---

### Task Sequence

There are exactly **2 tasks**, fully independent (no inter-task dependency — one touches `main.py`, one touches the test file). They can be done in a single commit.

---

#### TASK 1 — Add the `ping` endpoint
**Owner:** Backend  
**File:** `backend/app/main.py`  
**Change type:** Edit — insert 3 lines after line 238

**Exact insertion** (after `return {"status": "healthy"}`):

```python
@app.get(f"{settings.api_prefix}/ping")
async def ping() -> dict[str, str]:
    return {"ping": "ok"}
```

**Notes:**
- `f"{settings.api_prefix}/ping"` — follows the exact pattern of `health_check` on line 236; never hardcodes `/api/app`.
- Return type annotation `dict[str, str]` — explicit, satisfies `mypy`, consistent with how `root()` annotates nothing but `health_check` does not; adding it here is the safe, lint-clean choice.
- No new imports required — `settings` is already in scope at line 21.
- No authentication dependency, no DB dependency — FastAPI will not inject anything into a handler with no parameters.
- `ruff`, `mypy`, `bandit` will all pass: no unsafe operations, trivial type, no new dependencies.

---

#### TASK 2 — Add `test_ping`
**Owner:** Backend  
**File:** `backend/tests/test_main.py`  
**Change type:** Edit — append 7 lines at end of file

**Exact addition** (appended after the last line of `test_health_check`):

```python
@pytest.mark.asyncio
async def test_ping(client: AsyncClient) -> None:
    """Test ping endpoint."""
    response = await client.get(f"{settings.api_prefix}/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "ok"}
```

**Notes:**
- `@pytest.mark.asyncio` — matches the decoration on lines 5 and 15; required even though `asyncio_mode = "auto"` is set, because that is the established style in this file.
- `settings.api_prefix` — already imported on line 1; no hardcoded path string.
- `assert response.json() == {"ping": "ok"}` — exact equality, not a subset check; satisfies REQ-2 and AC-1.
- No `assert "Content-Type" in …` check needed for coverage (the route has no branches and the single `return` is covered by this one call).
- The `client` fixture brings a full test DB and auth overrides; the `/ping` handler ignores all of that, which is fine — the fixture is a superset of what the handler needs.

---

### What Is Explicitly NOT Touched

| File | Reason |
|---|---|
| `proxy/default.conf` | `location /api/app/` (line 42) already forwards all `/api/app/*` paths; no new block needed |
| Any file under `backend/app/api/` | No new router; inline `@app.get` is the correct pattern per REQ-4 |
| `backend/conftest.py` | `client` fixture is reused as-is |
| `backend/pyproject.toml` | No threshold changes ever |
| All frontend files | Out of scope per spec |
| `VERSION`, `CHANGELOG`, `docker-compose.prod.yml` | Infrastructure utility endpoint; no release required |

---

### Coverage Impact Analysis

| Line added in `main.py` | Covered by | Branch? |
|---|---|---|
| `@app.get(…)` decorator | Registration happens at import time — covered by module load | N/A |
| `async def ping() -> dict[str, str]:` | `test_ping` calls `GET /api/app/ping` | No branch |
| `return {"ping": "ok"}` | Same call | No branch |

`branch = true` is satisfied: the handler has no conditional paths. A single happy-path test achieves 100% line **and** branch coverage of the new code.

---

### Commit Message

```
feat(api): add GET /api/app/ping liveness endpoint

Adds a static ping endpoint at /api/app/ping that returns {"ping": "ok"}
with HTTP 200. No auth, no DB, no parameters.

Motivation: provides a cheap liveness signal that external probes or
load-balancer health checks can use without touching any backend logic.

Implementation:
- Inline @app.get on the FastAPI app object, matching the existing
  health_check pattern (main.py:236-238).
- Path constructed as f"{settings.api_prefix}/ping" — tracks config,
  never hardcoded.
- One new test (test_ping) in test_main.py; uses the existing client
  fixture and settings import; maintains 100% coverage.
- No proxy changes needed: the existing nginx location /api/app/ block
  already routes /api/app/ping to the backend.
```

---

### Verification Steps (in order, before marking done)

1. **Apply TASK 1** (edit `main.py` after line 238)
2. **Apply TASK 2** (append to `test_main.py`)
3. **`run_tests(backend)`** — confirm all three tests in `test_main.py` pass, coverage shows the new lines covered, no regressions
4. **CI** — push to branch, confirm "Prod Deployment" pipeline stays green across ruff → mypy → bandit → pytest → vitest stages


## 12:08:47 — Design (architect)

All facts are now grounded in reality. Here is the complete technical design.

---

## Technical Design — `GET /api/app/ping`

### Verified Ground Truth (Observed, Not Assumed)

| Fact | Source | Observed Value |
|---|---|---|
| `api_prefix` | `backend/app/config.py:11` | `"/api/app"` |
| `settings` imported in `main.py` | `main.py:21` | `from app.config import settings` ✓ |
| Inline route pattern | `main.py:236–238` | `@app.get(f"{settings.api_prefix}/health")` / `async def health_check()` / `return {"status": "healthy"}` |
| Exact insertion line | `main.py:238` | `return {"status": "healthy"}` — new block appended immediately after |
| `asyncio_mode = "auto"` | `pyproject.toml:8` | Present; yet all existing tests still carry `@pytest.mark.asyncio` — new test must match |
| `branch = true` | `pyproject.toml:25` | Present — zero-branch handler, one test covers it completely |
| No `--cov-fail-under` flag | `pyproject.toml` (grep) | Absent — 100% is enforced by team convention on report output |
| Test file imports | `test_main.py:1–3` | `settings`, `pytest`, `AsyncClient` — all required imports already present |
| `client` fixture | `conftest.py` | `async def client(db_session)` via `ASGITransport(app=app)` — reusable as-is |
| Proxy routing | `proxy/default.conf:42–49` | `location /api/app/ { proxy_pass http://backend:8000/api/app/; }` — already covers `/api/app/ping` |
| CI state | `gh run list --branch main` | Last completed run: **success** (`feat(agents): Anthropic…`); one run currently `in_progress` |

---

### Affected Components

| Component | Change | Scope |
|---|---|---|
| `backend/app/main.py` | +3 lines — one `@app.get` decorator + `async def ping()` + `return` | Additive only |
| `backend/tests/test_main.py` | +7 lines — `test_ping` function | Additive only |
| Everything else | **No change** | See "Not Touched" table below |

---

### New Interface / Contract

```
GET /api/app/ping
→ 200 OK
  Content-Type: application/json
  Body: {"ping": "ok"}
```

- **No path parameters, query parameters, or request body.**
- **No authentication dependency** — handler signature is empty; FastAPI injects nothing.
- **No database dependency** — zero I/O, pure static response.
- **No new imports** — `settings` already in scope at `main.py:21`.
- **Return type annotation** `dict[str, str]` — explicit, satisfies `mypy`, consistent with adding type safety without changing the runtime contract.

---

### Data Flow

```
External probe / load-balancer
        │
        │  GET /api/app/ping
        ▼
nginx (proxy/default.conf)
  location /api/app/  →  proxy_pass http://backend:8000/api/app/ping
        │
        ▼
FastAPI app (main.py)
  @app.get("/api/app/ping")
  async def ping() -> dict[str, str]
        │
        ▼
  return {"ping": "ok"}   ← no DB, no auth, no I/O
        │
        ▼
200 OK  {"ping": "ok"}
```

No middleware, no dependency injection chain, no async I/O. This is the absolute minimum path through the stack.

---

### Implementation Tasks (2, Independent — Single Commit)

#### TASK 1 — Endpoint (`backend/app/main.py`)
Insert exactly these 3 lines immediately after line 238 (`return {"status": "healthy"}`):
```python
@app.get(f"{settings.api_prefix}/ping")
async def ping() -> dict[str, str]:
    return {"ping": "ok"}
```

#### TASK 2 — Test (`backend/tests/test_main.py`)
Append exactly these 7 lines after the final line of `test_health_check`:
```python
@pytest.mark.asyncio
async def test_ping(client: AsyncClient) -> None:
    """Test ping endpoint."""
    response = await client.get(f"{settings.api_prefix}/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "ok"}
```

Both tasks touch different files with zero logical dependency between them.

---

### Coverage Impact

| New line | Covered by | Branch created? |
|---|---|---|
| `@app.get(…)` decorator | Module load at import time | No |
| `async def ping()` | `test_ping` HTTP call | No |
| `return {"ping": "ok"}` | Same call | No |

`branch = true` is fully satisfied: the handler has **no conditional paths**. One happy-path test achieves **100% line and branch coverage** of the new code with zero risk to existing coverage.

---

### What Is Explicitly NOT Touched

| File | Reason |
|---|---|
| `proxy/default.conf` | `location /api/app/` (line 42) already forwards all `/api/app/*` — confirmed by direct file read |
| `backend/app/api/*` | No new router — inline `@app.get` matches the `health_check` precedent exactly |
| `backend/conftest.py` | `client` fixture reused unchanged |
| `backend/pyproject.toml` | No threshold changes, ever |
| All frontend files | Out of scope |
| `VERSION`, `CHANGELOG`, `docker-compose.prod.yml` | Infrastructure utility endpoint; no release required |

---

### Trade-offs

| Decision | Alternative | Why This Way |
|---|---|---|
| Inline `@app.get` on `app` object | New `APIRouter` in `backend/app/api/` | Matches the established `health_check` pattern; a dedicated router adds a file and a `include_router` call for a 1-line handler — unjustified overhead |
| `dict[str, str]` return annotation | No annotation (like `health_check`) | Makes `mypy` fully happy with zero cost; `health_check` predates the stricter type convention |
| Reuse `client` fixture (brings DB + auth) | New lightweight fixture | Fixture is a superset; the handler ignores DB/auth entirely; no reason to introduce a second fixture class |
| `{"ping": "ok"}` exact equality assert | Subset check | Exact equality is stricter and matches the AC precisely — `{"ping": "ok"}` is the full contract |
| `@pytest.mark.asyncio` kept even with `asyncio_mode = "auto"` | Drop the decorator | All existing tests in this file carry it; removing it from the new test creates an inconsistency; decorating it matches the established style without any harm |

---

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Name collision with a future `ping` route in a router | Low | Medium | `@app.get` routes registered directly on `app` take precedence in FastAPI's routing order; trivial to spot in code review |
| Endpoint becomes a DDoS amplification vector (unauthenticated, no rate limiting) | Very low | Low | Response is 18 bytes, pure CPU-bound, no DB; amplification ratio is effectively zero; rate limiting at the nginx layer is the correct control plane if ever needed |
| CI run currently `in_progress` on `main` | Present | Low | The fix/agents commit is already in flight; both tasks are purely additive and touch no code the in-progress run modifies — no conflict expected |
| `asyncio_mode = "auto"` + `@pytest.mark.asyncio` double-decoration | Benign | None | Confirmed harmless by existing tests (lines 5, 15) which already carry the same decoration under `auto` mode |

---

### Commit Message

```
feat(api): add GET /api/app/ping liveness endpoint

Adds a static ping endpoint at /api/app/ping returning {"ping": "ok"}
with HTTP 200. No auth, no DB, no parameters.

Motivation: cheap liveness signal for external probes and load-balancer
health checks that requires no backend logic and has zero I/O cost.

Changes:
- main.py: inline @app.get after health_check, same pattern/style;
  path uses settings.api_prefix (never hardcoded).
- test_main.py: test_ping appended; uses existing client fixture and
  settings import; maintains 100% line + branch coverage.
- No proxy changes: nginx location /api/app/ already routes /api/app/ping.
```


## 12:09:02 — Stories (story-writer)

## User Stories

---

### Story 1 — Liveness Probe

**As a** platform engineer,
**I want** a `GET /api/app/ping` endpoint that returns `{"ping": "ok"}`,
**so that** load balancers and monitoring tools can confirm the backend process is alive without touching the database or requiring authentication.

**Acceptance Criteria:**

- **Given** the backend is running, **When** `GET /api/app/ping` is called with no headers, body, or auth token, **Then** the response is HTTP 200 with body `{"ping": "ok"}` and `Content-Type: application/json`.
- **Given** a request with no `Authorization` header or session cookie, **When** `GET /api/app/ping` is called, **Then** HTTP 200 is returned (not 401 or 403).
- **Given** the full docker-compose stack, **When** `GET https://mavrov.de/api/app/ping` is called through nginx, **Then** the existing `/api/app/` proxy rule forwards it to the backend and returns HTTP 200 `{"ping": "ok"}` end-to-end — with zero changes to `proxy/default.conf`.

---

### Story 2 — Test Coverage & CI Safety

**As a** backend developer,
**I want** a `test_ping` test in `backend/tests/test_main.py` that asserts the contract of the ping endpoint,
**so that** CI enforces the 100% coverage rule and no regression can silently break the liveness probe.

**Acceptance Criteria:**

- **Given** the test suite, **When** `pytest` runs, **Then** `test_ping` passes asserting `status_code == 200` and `response.json() == {"ping": "ok"}` (exact equality, no extra keys).
- **Given** the existing tests, **When** `test_ping` is added, **Then** `test_root_endpoint` and `test_health_check` still pass unchanged.
- **Given** the new endpoint code, **When** `pytest --cov=app --cov-report=term-missing` runs, **Then** the new lines in `main.py` appear as covered and overall coverage does not decrease.
- **Given** the codebase, **When** `ruff check` and `mypy` run against `main.py`, **Then** both exit 0 with no new violations or type errors.

---

### Story 3 — Implementation Consistency

**As a** backend developer,
**I want** the ping endpoint implemented as an inline `@app.get` using `settings.api_prefix` (not a hardcoded string or a new `APIRouter`),
**so that** the pattern stays consistent with the existing `/health` route and the prefix remains a single source of truth.

**Acceptance Criteria:**

- **Given** `main.py`, **When** the endpoint is added, **Then** the path is constructed as `f"{settings.api_prefix}/ping"` — no hardcoded `/api/app/ping` string literal appears.
- **Given** the endpoint definition, **When** it is reviewed, **Then** it is an `async def` decorated with `@app.get` directly on the `app` object — no new file, no new `APIRouter`, no new import is added to `main.py`.
- **Given** a `POST /api/app/ping` request, **When** it is sent, **Then** FastAPI returns HTTP 405 Method Not Allowed (default framework behaviour — no extra code required).


## 12:09:46 — Implement (backend) (backend-dev)

## Done

Both changes have been applied to the worktree:

### `backend/app/main.py` — lines 241–243 added
```python
@app.get(f"{settings.api_prefix}/ping")
async def ping() -> dict[str, str]:
    return {"ping": "ok"}
```

### `backend/tests/test_main.py` — `test_ping` appended
```python
@pytest.mark.asyncio
async def test_ping(client: AsyncClient) -> None:
    """Test ping endpoint."""
    response = await client.get(f"{settings.api_prefix}/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "ok"}
```

### Status

The edits are confirmed applied (verified by `grep` and `read_file` after each edit). Test execution was blocked — the local agent environment has Python 3.9.6, but the project requires Python 3.13 (the `X | None` union syntax in `cv_request.py` fails on 3.9). **This is a pre-existing environment constraint, not caused by these changes.**

The implementation is correct and will pass in CI (Python 3.13):
- Zero-branch handler → one happy-path call covers 100% line + branch coverage
- No new imports, no hardcoded paths, matches `health_check` pattern exactly
- nginx `location /api/app/` already routes `/api/app/ping` — no proxy change needed

**Verify by pushing to CI** where the real Python 3.13 environment will run `pytest` cleanly.


## 12:10:29 — Implement (frontend) (frontend-dev)

## Status: Done

Both implementation tasks were already applied in this worktree before I began. Here is what I verified with tools:

### Observed State

**`backend/app/main.py` lines 241–243** (observed via `grep -n`):
```python
@app.get(f"{settings.api_prefix}/ping")
async def ping() -> dict[str, str]:
    return {"ping": "ok"}
```
- Placed immediately after `health_check` (lines 236–238) — exact correct position
- Path uses `settings.api_prefix` — never hardcoded
- Return type `dict[str, str]` — satisfies mypy
- No new imports needed (`settings` already in scope at line 21)

**`backend/tests/test_main.py`** (observed via `read_file`):
```python
@pytest.mark.asyncio
async def test_ping(client: AsyncClient) -> None:
    """Test ping endpoint."""
    response = await client.get(f"{settings.api_prefix}/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "ok"}
```
- `@pytest.mark.asyncio` — matches the decoration style of all existing tests in the file
- `settings.api_prefix` — uses the already-imported constant, no hardcoded path
- Exact equality assert on `{"ping": "ok"}` — matches the contract precisely

### What I Could Not Do
The test runner requires `TESTING=true` as an environment variable prefix, which is blocked in this environment. **I cannot claim the tests pass** — that must be verified in CI or by a human running `TESTING=true pytest backend/tests/test_main.py -v` locally.

### What Is Confirmed
- The endpoint implementation is correct and complete
- The test is correctly structured and covers the single execution path (zero branches)
- No other files need changes (nginx `location /api/app/` already routes `/api/app/ping`)


## 12:12:40 — Test gate (attempt 1)

[backend] PASS
    0   100%
backend/app/api/tags.py                 52      0   100%
backend/app/api/years.py                51      0   100%
backend/app/config.py                   30      0   100%
backend/app/database.py                 10      0   100%
backend/app/logger.py                    6      0   100%
backend/app/main.py                    114      0   100%
backend/app/models/__init__.py           4      0   100%
backend/app/models/cv_document.py       13      0   100%
backend/app/models/cv_request.py        20      0   100%
backend/app/models/post.py              32      0   100%
backend/app/models/user.py              16      0   100%
backend/app/services/__init__.py         0      0   100%
backend/app/services/ai.py             220      0   100%
backend/app/services/auth.py            70      0   100%
backend/app/services/chat.py            30      0   100%
backend/app/services/email.py           43      0   100%
backend/app/services/embeddings.py      15      0   100%
backend/app/services/linkedin.py       116      0   100%
backend/app/services/multi_chat.py     154      0   100%
------------------------------------------------------------------
TOTAL                                 1865      1    99%
Coverage HTML written to dir htmlcov
Required test coverage of 95% reached. Total coverage: 99.95%
================== 606 passed, 7 skipped in 128.47s (0:02:08) ==================


> **Critical decision (12:12:40):** Deterministic test gate (≥95% coverage): GREEN.


## 12:13:24 — Code review (code-reviewer)

## Code Review

### Summary
The diff adds a `/ping` endpoint to the FastAPI backend with a corresponding test. The change is minimal and surgical.

---

### Findings

#### Correctness
- **Endpoint logic**: `{"ping": "ok"}` is a valid, correctly typed response matching the declared `-> dict[str, str]` return type annotation. ✓
- **Route registration**: Uses the same `f"{settings.api_prefix}/ping"` pattern as the adjacent `/health` endpoint. Consistent and correct. ✓
- **Test fixture**: Uses the shared `client: AsyncClient` fixture from `backend/conftest.py`, which properly wires the test DB, auth overrides, and ASGI transport. ✓
- **Test assertion**: Asserts both `status_code == 200` and the exact JSON body `{"ping": "ok"}`. Full and precise. ✓

#### Style / Quality
- **Inconsistency in return type annotation**: `health_check()` has no return type annotation; `ping()` adds `-> dict[str, str]`. This is a minor style inconsistency with the immediately adjacent endpoint, but it is strictly an improvement — not a regression.
- **Test docstring**: Present and clear. ✓
- **`@pytest.mark.asyncio`**: Correctly applied, consistent with sibling tests in the same file. ✓
- **No functional overlap**: `/ping` and `/health` serve different semantics (liveness probe vs. health check). The distinction is thin but acceptable for this codebase.

#### Security
No security concerns. The endpoint returns a static string, takes no input, has no authentication side-effects.

#### Coverage
The new test covers the new endpoint 1:1. Coverage is maintained at 100%. ✓

---

### Verdict

APPROVE


## 12:14:05 — Security review (security-reviewer)

I now have everything I need. Here is the full security review.

---

## Security Review — `/ping` Endpoint Addition

### What the diff does
Adds a new unauthenticated `GET /api/app/ping` endpoint that returns the static literal `{"ping": "ok"}`, plus a corresponding test. That is the complete scope of the change.

---

### Finding-by-finding Analysis

#### 1. Information Disclosure — NONE
The response body is a hardcoded string literal. It reveals nothing about the host, version, runtime, DB state, or internal topology. This is strictly less informative than the already-existing `/api/app/health` endpoint (same pattern, same posture) and far less than `/api/app/stats/public` which already exposes `visitor_ip`, `backend_version`, and `uptime` to the unauthenticated public.

**Verdict:** No new information disclosure.

#### 2. Authentication / Authorisation — N/A by design
The endpoint carries no `Depends(get_current_user)` / `Depends(get_current_admin_user)` guard, which is correct for a liveness probe. The pre-existing `/health` endpoint follows identical posture; both are at `GET` with no side effects. Kubernetes/load-balancer probes *require* unauthenticated liveness checks. Requiring auth here would be wrong.

**Verdict:** Intentionally unauthenticated; matches existing pattern; no authz gap.

#### 3. Injection Risk — NONE
The handler takes zero input, performs zero DB operations, executes zero shell or SQL commands, and returns a static dict. There is nothing to inject into.

**Verdict:** Zero attack surface for injection.

#### 4. Rate-Limiting / DoS Amplification — TOLERABLE
There is no application-level rate limiter (confirmed: no `slowapi`/`limiter` import anywhere in the project). This is already true for `/health` and every other endpoint. The `/ping` endpoint is not meaningfully cheaper or more expensive than `/health`; it does not touch the DB or any downstream service. Any DoS concern is infrastructure-level (reverse proxy, WAF) and is not introduced by this diff.

**Verdict:** No new DoS surface relative to the existing baseline.

#### 5. Route Conflicts / Path Confusion — NONE
`/api/app/ping` does not shadow, prefix, or conflict with any existing route. Confirmed by grepping the full router list.

**Verdict:** No routing anomaly.

#### 6. Secrets / Credential Exposure — NONE
No environment variables, tokens, or config values are accessed or echoed.

**Verdict:** Clean.

#### 7. Test Quality
- The test exercises a real `AsyncClient` against the live ASGI app (same fixture as `test_health_check`).
- It asserts both status code **and** exact response body — adequate for a static endpoint.
- `@pytest.mark.asyncio` and return-type annotation are consistent with the rest of the file.
- The test maintains 100% coverage for the new code path.

**Verdict:** Test is correct and sufficient.

#### 8. Broader Context Observations (not blocking, informational)
These are pre-existing issues unrelated to this diff but worth flagging for the team:

- `config.py` contains `jwt_secret_key: str = "your-secret-key-change-in-production"` as a hardcoded default. This is a **separate, pre-existing critical finding** — not introduced here.
- `default_admin_password: str = "admin"` in config is another pre-existing weak-default credential.
- `stats/public` leaks `visitor_ip` and `backend_version` without auth — pre-existing.

None of these are introduced or worsened by this diff.

---

### Summary Table

| Category | Risk | Introduced by diff? |
|---|---|---|
| Information disclosure | None | No |
| Auth/Authz bypass | None | No |
| Injection | None | No |
| DoS amplification | Tolerable (infra concern) | No |
| Secrets exposure | None | No |
| Route conflict | None | No |
| Test coverage | 100% maintained | ✅ |

---

The diff is a minimal, correct, zero-side-effect liveness probe endpoint, consistent in every respect with the pre-existing `/health` endpoint. There are no security objections to this change.

**APPROVE**


> **Critical decision (12:14:05):** Reviews — code: APPROVE/GO, security: APPROVE/GO => APPROVED.


## 12:14:44 — Documentation (documentation-writer)

Here are the three documentation updates, grounded in what I actually read from the repo.

---

## 1. `CHANGELOG.md` — updated `[Unreleased]` entry


## 12:15:23 — Release decision (release-manager)

(agent 'release-manager' unavailable: HTTP Error 503: Network communication error fetching agent card from http://localhost:8021/.well-known/agent.json: )


> **Critical decision (12:15:23):** Release Manager: NO-GO — (agent 'release-manager' unavailable: HTTP Error 503: Network communication error fetching agent card from http://localh


## Critical decisions (summary)

- **12:12:40** Deterministic test gate (≥95% coverage): GREEN.
- **12:14:05** Reviews — code: APPROVE/GO, security: APPROVE/GO => APPROVED.
- **12:15:23** Release Manager: NO-GO — (agent 'release-manager' unavailable: HTTP Error 503: Network communication error fetching agent card from http://localh
