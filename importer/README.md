# LinkedIn importer

A small, **stable, standalone** process that pushes your LinkedIn posts into mavrov.de.
It is **not** part of the `agents/` A2A team and has no dependency on it.

```
scraper/posts_data.json  ──►  importer  ──►  POST /api/app/linkedin/import-post
        (spec 05)              (this)          (spec 04, upserts by URN)
```

For each post it: skips it if unchanged (local ledger), downloads its image with your
saved LinkedIn session, and POSTs text + image to the ingest endpoint with the machine
token. It is **idempotent** (URN upsert on the server + `state.json` ledger), **retries**
with backoff (one bad post never aborts the batch), imports **oldest → newest**, and
exits non-zero if any post hard-failed (so cron can alert).

## Run

```bash
pip install -r importer/requirements.txt

export MAVROV_API_URL=https://mavrov.de           # or http://localhost:8000
export LINKEDIN_IMPORT_TOKEN=...                  # must match the backend
export LINKEDIN_COOKIE_LI_AT=...                  # for authenticated image downloads
# posts come from scraper/posts_data.json (run `npm run scrape:posts` first — spec 05)

python -m importer --dry-run     # preview: does everything except POST (safe vs prod)
python -m importer               # one-shot import
python -m importer --watch 3600  # re-run hourly
```

Imported posts are **drafts** by default (review, then publish); pass `--publish` to import
as published. See `specs/done/linkedin-import-FULL-reference.md` §Component 3 / §1d for the full design
and the prod-connection modes.

## Config (env)

| var | default | meaning |
|-----|---------|---------|
| `MAVROV_API_URL` | `http://localhost:8000` | backend base URL |
| `LINKEDIN_IMPORT_TOKEN` | — | machine token (matches backend) |
| `LINKEDIN_COOKIE_LI_AT` | — | LinkedIn session cookie for image downloads |
| `POSTS_JSON` | `scraper/posts_data.json` | scraped posts input |
| `IMPORT_STATE` | `importer/state.json` | processed-URN ledger |
| `IMPORT_PUBLISH` | `false` | import as published vs draft |
| `IMPORT_RETRIES` / `IMPORT_BACKOFF` | `3` / `1.0` | retry policy |

## Test

```bash
pytest importer/tests -q     # mocked HTTP, no live LinkedIn/prod
```
