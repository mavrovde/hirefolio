# Add a build-info field to the health endpoint

## Summary
Expose the app version on the health check so ops can verify what's deployed.

## Scope
- **In:** add a `version` field to the existing `GET /api/app/health` response.
- **Out:** no new endpoint, no auth changes, no frontend changes.

## Contract / behaviour
- `GET /api/app/health` → `200 {"status": "healthy", "version": "<app.version>"}`
  (use the FastAPI `app.version` already set in `backend/app/main.py`).

## Acceptance criteria (testable)
- [ ] `GET /api/app/health` returns `status` == "healthy" AND a non-empty `version`.
- [ ] The existing health test still passes; other endpoints unaffected.
- [ ] A test asserts the `version` field; backend coverage maintained.

## Notes / constraints
- Edit the existing `health_check` handler surgically; do not add a new router.

<!-- This is a filled EXAMPLE (kept in specs/, not specs/inbox/, so it isn't processed).
     To use it: copy into specs/inbox/add-version-to-health.md -->
