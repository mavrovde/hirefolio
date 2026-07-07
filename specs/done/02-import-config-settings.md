# Add import settings (machine token + max image size)

## Summary
Add two configuration fields the upcoming LinkedIn import endpoint will need. Tiny, self-contained
(same shape as adding any other `Settings` field).

## Scope
- **In:** add to `Settings` in `backend/app/config.py`:
  - `linkedin_import_token: str = ""` — machine auth token for the import endpoint (empty = disabled).
  - `import_max_image_mb: int = 10` — image size cap for the import endpoint.
- **Out:** no endpoint yet, no auth logic — just the settings fields and their tests.

## Contract / behaviour
- `settings.linkedin_import_token` defaults to `""`.
- `settings.import_max_image_mb` defaults to `10`.
- Both overridable via environment variables (pydantic-settings), like the existing fields.

## Acceptance criteria (testable)
- [ ] `Settings()` exposes `linkedin_import_token` (default `""`) and `import_max_image_mb` (default `10`).
- [ ] A test in `backend/tests/test_config.py` asserts both defaults.
- [ ] Existing config tests pass; backend coverage stays at 100%.

## Notes / constraints
- Mirror the style of the existing `linkedin_*` settings already in `config.py`. Minimal change,
  no other files touched.
</content>


---
## Intake result (2026-07-06 16:43)
- branch: `agent/02-import-config-settings`
- gate green: True
- outcome: opened PR: https://github.com/mavrovde/mavrov.de/pull/8
- run log: `docs/agent-runs/02-import-config-settings-20260706-163011.md`
