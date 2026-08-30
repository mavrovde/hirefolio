---
mode: agent
description: Run the full local quality gates the way CI/verify_all.sh does — backend, frontend, and Docker E2E
---

Run the project's full verification suite (mirrors `./verify_all.sh` + CI `deploy.yml`) and report
a concise pass/fail table. Do NOT push anything. Fix root causes (no band-aids) and re-run the
affected stage on failure.

Preconditions:
- `pgrep -f pytest` must return nothing — never run backend pytest while another suite is active
  (the shared `test_mavrov` DB clobbers concurrent suites). Wait if needed.
- If a gate fails, reproduce it on an unmodified `main` build (git worktree) before blaming the
  current diff — it may be a latent gate bug.

1. Backend (`cd backend`, use `venv/bin`; Postgres on `127.0.0.1:5433`, a `test_*` DB via
   `TEST_DATABASE_URL`, `HIREFOLIO_GEMINI_API_KEY=""`):
   `ruff check .` · `ruff format --check .` · `mypy app --ignore-missing-imports
   --no-error-summary` · `bandit -r app -ll --skip B101` · `pytest` (100% coverage).
2. Frontend (`cd frontend`):
   `npm run lint --if-present` · `npm run test:coverage` (100% per project) · `npm run build`
   (shared → public → admin).
3. Docker E2E (required for SSR/HTTP/proxy-affecting changes):
   `docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml up -d --build backend
   frontend proxy open-webui`, wait for health, seed the E2E user
   (`scripts/seed_e2e_user.py`), run `PROXY_PORT=80 python3 verify_proxy_routes.py`, then
   `cd frontend && CI=true BASE_URL=http://localhost npx playwright test --grep-invert "profile"`.
   Note: the proxy's HTTPS is on host port 10443 (`https://localhost:10443`).
   Tear down with `docker compose ... down` (NEVER with `-v`/`--volumes`).
