---
description: Run the full Docker E2E the known-good way — prod-topology up, real readiness gate, seed, public-e2e, counts
---

Run the repo's full Docker E2E loop exactly as codified in the **`e2e-validation` skill**
(`.claude/skills/e2e-validation/SKILL.md`) — load it first and follow it precisely; do not
re-derive the steps. Summary of the loop it defines:

1. Precondition: `pgrep -f pytest` is empty (shared `test_hirefolio` DB — lessons-learned §4).
2. `docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml up -d --build backend frontend admin-frontend proxy open-webui`
3. **Readiness gate** (retry up to ~120 s; the third check is what prevents the pre-schema
   `relation "profile_snapshots" does not exist` 500 race):
   `curl -sf http://localhost/health` → `curl -sf http://localhost/` → `curl -sf http://localhost/api/app/stats/public`
4. Seed **in-container only**: `… exec -T backend python scripts/seed_e2e_user.py`
5. `cd frontend && CI=true BASE_URL=http://localhost npx playwright test --project=public-e2e`
   (add `admin-e2e` with `ADMIN_BASE_URL=http://admin.localhost` when admin flows are in scope).
   Run the whole project, never a spec subset.
6. Report pass/fail counts. Teardown `… down` only if asked — and **never `down -v`**.

Known trap to surface instead of "fixing": if open-webui crash-loops with nginx
`host not found in upstream "open-webui"`, the volume schema is newer than the pinned image —
bump the image pin forward (#123 precedent); **never delete the volume** (rule 9; the
guard hook will block it, and a backup is not consent). A red E2E must be reproduced on an
unmodified `main` build before blaming the current diff (lessons-learned §13). $ARGUMENTS
