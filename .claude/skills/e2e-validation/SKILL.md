---
name: e2e-validation
description: >-
  The known-good full Docker E2E loop for mavrov.de — prod-topology bring-up, REAL readiness
  gating (not just container health), E2E seeding, Playwright run, and the recurring traps
  (open-webui volume/schema crash-loop, pre-schema 500 race, shared test-DB clobbering). Consult
  before running or debugging the Docker E2E — it is the only gate that catches SSR/zoneless
  regressions, and the most error-prone to run by hand. The `/e2e` command executes this loop.
---

# E2E validation — the known-good loop (#117)

The Docker E2E is the repo's most important gate (the only one that catches SSR / zoneless-CD /
transfer-cache regressions — lessons-learned §1–§3) and the most error-prone to run by hand.
This is the exact sequence; `/e2e` runs it.

## 0. Preconditions
- `pgrep -f pytest` → empty. Never run alongside a backend pytest suite: both reset the shared
  `test_mavrov` DB and clobber each other (lessons-learned §4).
- Docker daemon up; ~4 GB free (images + ollama models; models persist in `ollama_data`, so only
  the first run pays the pull).

## 1. Build + bring up the prod topology
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml up -d --build backend frontend admin-frontend proxy open-webui
```
The `e2e.yml` overlay builds images locally and opens `ADMIN_ALLOWED_CIDRS=0.0.0.0/0` (a plain
prod-compose stack 403s non-loopback admin requests).

## 2. Readiness is an APPLICATION property, not a container state
Waiting on container health alone admits the **pre-schema race**: the backend serves
`/api/app/profile` before schema init finishes → transient
`500 relation "profile_snapshots" does not exist`, which reads as a mystery red. Gate on all three,
in order, with retries (e.g. up to ~120 s):
```bash
curl -sf http://localhost/health                       # THE schema gate: 503 until schema_ready() (#124)
curl -sf http://localhost/ >/dev/null                  # frontend SSR serving
curl -sf http://localhost/api/app/stats/public         # end-to-end proxy→backend request works
```
Only after all three: seed. Note which check does what: `/health` is the real schema gate — it
returns **503 until `schema_ready()`** (`backend/app/main.py`, #124) — while the stats call proves
the proxied request path, not the schema.

## 3. Seed E2E data (in-container — it wipes and recreates the users table in THAT stack's DB)
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml exec -T backend python scripts/seed_e2e_user.py
```
NEVER run `seed_e2e_user.py` against the live dev DB — it obliterates all users (posts have no FK to users, but the wiped admin locks you out).

## 4. Run Playwright
```bash
cd frontend && CI=true BASE_URL=http://localhost npx playwright test --project=public-e2e
# admin flows: ADMIN_BASE_URL=http://admin.localhost npx playwright test --project=admin-e2e
# (/verify's historical invocation adds --grep-invert "profile" — drop it only
# when profile specs are in scope for your change)
```
Run the WHOLE project, not a spec subset — a stale spec asserting removed behavior is exactly what
a subset run misses (lessons-learned §3, the #108→#110 fix-forward). Report pass/fail counts.

## 5. Teardown (optional — keep the stack for debugging)
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml down     # NO -v. Ever.
```

## Recurring traps
- **open-webui volume/schema crash-loop.** The pinned image (`docker-compose.prod.yml` `open-webui`,
  v0.11.0 since #123/#155) crash-loops if the `open-webui` volume holds a NEWER schema than the
  image, and nginx then fails with `host not found in upstream "open-webui"`. The fix is to bump
  the pinned image FORWARD to match the volume — **never wipe the volume** (`docker volume rm` /
  `down -v` are rule-9 violations; the guard hook blocks them, and a backup is not consent).
- **A failing E2E is not proof your diff broke it.** Reproduce on an unmodified `main` build first
  (lessons-learned §13) — stack state, flaky external pulls, and stale volumes all fail
  independently of your change.
- **HTTPS lives on host port 10443** (`https://localhost:10443`); a plain `https://localhost/`
  curl returns `000` — not a failure.
- **Proxy route audit**: `PROXY_PORT=80 python3 verify_proxy_routes.py` (needs the e2e overlay for
  the admin-host check, see step 1).
