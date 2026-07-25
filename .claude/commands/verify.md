---
description: Run the full local quality gates (backend + frontend) the way CI does
---

Run the project's quality gates and report a concise pass/fail table. Do NOT push anything.

Backend (`cd backend`, use `venv/bin`), against Postgres on `127.0.0.1:5433` (a `test_*` DB via
`TEST_DATABASE_URL`/`DATABASE_URL`):
1. `ruff check .`
2. `ruff format --check .`
3. `mypy app --ignore-missing-imports --no-error-summary`
4. `bandit -r app -ll --skip B101`
5. `pytest` (keep coverage ≥95%; the project standard is 100%)

Frontend (`cd frontend`):
6. `npm test -- --watch=false --coverage`
7. `npm run build`

Report each gate's result. If any fail, diagnose the root cause (no band-aids) and fix, then
re-run only the affected gate. $ARGUMENTS
