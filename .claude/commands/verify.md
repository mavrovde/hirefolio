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
12. Proxy routes: `PROXY_PORT=80 python3 verify_proxy_routes.py`
13. Playwright: `cd frontend && CI=true BASE_URL=http://localhost npx playwright test --grep-invert "profile"`
14. Tear down when done: `docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml down`

Notes / caveats:
- `verify_all.sh` orchestrates all of the above, but line ~26 hardcodes a conda python path
  (`/Users/sergii.mavrov/...`) — make it portable (`backend/venv` or `python3`) before relying on it.
- On a slow link the in-container Ollama model pulls dominate E2E wall-clock; models persist in the
  `ollama_data` volume, so subsequent runs are fast.
- CI (`deploy.yml`) runs this same E2E on clean runners on push to `main`.
