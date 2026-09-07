---
description: Run the full local quality gates the way CI/verify_all.sh does — backend, frontend, AND Docker E2E
---

Run the project's full verification suite (mirrors `./verify_all.sh` + CI `deploy.yml`) and report a
concise pass/fail table. Do NOT push anything. Fix root causes (no band-aids) and re-run the
affected stage on failure. $ARGUMENTS

## 1. Backend (`cd backend`, use `venv/bin`)
Against Postgres on `127.0.0.1:5433` (a `test_*` DB via `TEST_DATABASE_URL`/`DATABASE_URL`):
1. `ruff check .`
2. `ruff format --check .`
3. `mypy app --ignore-missing-imports --no-error-summary`
4. `bandit -r app -ll --skip B101`
5. `pytest` (keep coverage ≥95%; project standard is 100%)

## 2. Frontend (`cd frontend`)
6. `npm run lint --if-present`
7. `npm test -- --watch=false --coverage` (100% coverage)
8. `npm run build`

## 3. End-to-End (Docker stack) — required
9. Build + start the full prod-topology stack:
   `docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml up -d --build backend frontend proxy open-webui`
   (the `e2e.yml` override builds images locally; `db` + `ollama` start too — ollama must become
   healthy, which needs its models present/pulled).
10. Wait for health: backend `http://localhost/health`, frontend `http://localhost`, open-webui
    `http://localhost/open/health`.
11. Seed E2E data: `docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml exec -T backend python scripts/seed_e2e_user.py`
12. Proxy routes: `PROXY_PORT=80 python3 verify_proxy_routes.py` — the "Admin Host Login Route"
    check needs the E2E overlay's `ADMIN_ALLOWED_CIDRS=0.0.0.0/0` (docker-compose.e2e.yml);
    against a plain prod-compose stack the admin allowlist denies non-loopback with 403.
13. Playwright: `cd frontend && CI=true BASE_URL=http://localhost npx playwright test --grep-invert "profile"`
14. Tear down when done: `docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml down`

Notes / caveats:
- The proxy's HTTPS is published on host port **10443** (`https://localhost:10443`; `PROXY_SSL_PORT`
  in `verify_proxy_routes.py`) — a plain `https://localhost/` curl returns `000`.
- Never start this while another pytest suite is running — `pgrep -f pytest` first; two suites on
  the shared `test_hirefolio` DB clobber each other (lessons-learned §4).
- A failing gate is not proof the current diff broke it — reproduce on an unmodified `main` build
  before root-causing inside the diff (lessons-learned §13).
- `verify_all.sh` orchestrates all of the above. It runs backend pytest with a portable interpreter
  (`backend/venv/bin/python` if present, else `python3`); override with `PYTEST_PYTHON=/path/to/python`.
- On a slow link the in-container Ollama model pulls dominate E2E wall-clock; models persist in the
  `ollama_data` volume, so subsequent runs are fast.
- CI (`deploy.yml`) runs this same E2E on clean runners on push to `main`.
