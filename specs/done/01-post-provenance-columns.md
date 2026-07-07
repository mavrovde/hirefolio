# Add LinkedIn provenance columns to the Post model

## Summary
Add three nullable columns to `Post` so LinkedIn imports can be idempotent (dedup by URN) and
keep the original post date/link. No behaviour change to existing posts or endpoints.

## Scope
- **In:** add to `backend/app/models/post.py`:
  - `source_urn: Optional[str]` (String, nullable) — LinkedIn activity URN; **unique when not null**.
  - `source_url: Optional[str]` (String(512), nullable) — the LinkedIn permalink.
  - `posted_at: Optional[datetime]` (DateTime(timezone=True), nullable) — original publish time.
  - An Alembic migration under `backend/migrations/versions/` adding these + a unique index on
    `source_urn` (partial: `WHERE source_urn IS NOT NULL`).
- **Out:** no endpoint, no import logic, no change to `PostResponse`/existing behaviour.

## Contract / behaviour
- New columns are all nullable; existing rows get NULLs (backward compatible).
- Two posts may both have `source_urn IS NULL`; two non-null `source_urn` values must be unique.

## Acceptance criteria (testable)
- [ ] `Post` has `source_urn`, `source_url`, `posted_at`, all nullable.
- [ ] A test creates a `Post` with a `source_urn`, and a second insert with the **same** non-null
      `source_urn` raises an integrity error (unique enforced); two NULLs are allowed.
- [ ] Existing post tests/endpoints are unaffected; backend suite stays green at 100%.
- [ ] The migration has both `upgrade()` and `downgrade()`.

## Notes / constraints
- There are already 2 migrations; add a **third** that revises the current head (check
  `backend/migrations/versions/` for the latest `down_revision`). `env.py` uses async Alembic
  with asyncpg.
- Keep it minimal — only the model + migration + one focused test. Do not touch unrelated files.
</content>


---
## Intake result (2026-07-06 16:10)
- branch: `agent/01-post-provenance-columns`
- gate green: True
- outcome: opened PR: https://github.com/mavrovde/mavrov.de/pull/7
- run log: `docs/agent-runs/01-post-provenance-columns-20260706-155654.md`
