---
applyTo: "backend/**"
---

# Backend (FastAPI / Python)

- Python **3.12** in prod/CI (local venv at `backend/venv` may be 3.13). Run tools via
  `backend/venv/bin/...`.
- SQLAlchemy 2 **async** everywhere; PostgreSQL 16 + pgvector. All I/O is `async`/`await` —
  never block the event loop.
- **Pydantic models for every request/response schema.** No untyped dicts, no `Any`.
- Use FastAPI `Depends()` for dependencies; never hardcode them.
- Never expose raw stack traces to clients: catch, log with context, return a standard REST
  error model.

## Tests & gates (all must pass before a PR)

- `pytest` with **100% coverage** (`--cov=app`); cover error paths (400/401/404/409/429/500,
  timeouts, rollbacks), not just happy paths. Regression test for every bug fixed.
- Needs Postgres on `127.0.0.1:5433` and
  `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/test_mavrov` plus
  `GEMINI_API_KEY=""`. Without `TEST_DATABASE_URL` the suite targets the live dev DB and hangs.
- **Never run pytest while another suite is active** — `pgrep -f pytest` first and wait; two
  suites clobber the shared `test_mavrov` DB.
- `conftest.py` mocks heavy native libs (numpy, pgvector) — do not
  install them or bypass the mocks with module-load imports.
- Lint/format: `ruff check .` && `ruff format --check .` · Types: `mypy app
  --ignore-missing-imports --no-error-summary` · Security: `bandit -r app -ll --skip B101`
  (`# nosec` only for verified false positives, with a why-comment).
- Never lower coverage thresholds, skip tests, or add blanket ignores. Fix the code.
- Never authenticate to a paid/metered service with a real credential in any test — mock it or
  use an empty/dummy key so the free local fallback (Ollama) is taken.
- Keep `requirements.txt` and `requirements-dev.txt` in sync; `linkedin-api` stays `2.2.1`;
  within-major upgrades only.
