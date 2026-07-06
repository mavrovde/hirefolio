# Standalone LinkedIn importer (stable, NOT part of the A2A team)

> ⚠️ OUTSIDE the deterministic test gate (standalone process). Largest of the pieces. The team's
> green gate will NOT prove it end-to-end — verify with `--dry-run` + mocked tests, or build directly.

## Summary
A small, stable process (own folder `importer/`, own deps, own tests) that drives the scraper,
downloads each post's images with the LinkedIn session, and pushes them to the ingest endpoint.
Idempotent, retrying, logged — and completely independent of `agents/`.

## Prerequisites (on main)
- 04: `POST /api/app/linkedin/import-post` deployed. 05: scraper emits the posts JSON contract.

## Scope
- **In:** `importer/` (recommended Python — reuses httpx/pytest). One run: read/produce
  `posts_data.json` → normalize + detect language (en/de) → download image bytes (LinkedIn session)
  → `POST …/import-post` with `X-Import-Token` → per-post result. Idempotent (URN upsert + local
  `state.json` ledger), retries w/ backoff (one failure doesn't abort the batch), oldest→newest,
  run-summary + non-zero exit on hard failure. CLI: one-shot, `--watch <seconds>`, **`--dry-run`**.
- **Out:** no changes to `agents/`; profile/CV sync deferred to a later phase.

## Connecting to prod
- Mode A (recommended): runs on your machine → `MAVROV_API_URL=https://mavrov.de` over TLS with
  `X-Import-Token`. Mode B: a container on the prod `app-network` → `http://backend:8000`.
- Requires `LINKEDIN_IMPORT_TOKEN` set on the **backend** service in `docker-compose.prod.yml`
  and the same value given to the importer. See `_full-reference.md` §1d.

## Acceptance criteria (testable)
- [ ] Against a **mocked** backend + fixture `posts_data.json`: imports each post once, downloads
      images (mocked), logs a per-post result.
- [ ] A single mocked-500 post is retried then skipped; the batch continues and the exit code reports it.
- [ ] A second run over the same input imports nothing new (idempotent via ledger + URN upsert).
- [ ] `--dry-run` posts nothing. A guard test asserts the importer has **no import of `agents/`**.

## Notes / constraints
- Full behaviour, env vars, and test strategy in `_full-reference.md` §Component 3 / §Test strategy.
- Do not commit secrets, cookies, sessions, or scraped content.
</content>
