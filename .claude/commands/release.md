---
description: Prepare a release — verify green, bump version, update changelog, open PR (deploy = merge to main)
---

Prepare a release. Deploy happens by merging to `main` (GitHub Actions `deploy.yml` builds images
and runs `docker compose -f docker-compose.prod.yml up -d`). Do NOT push to `main` directly or run
`release.sh` here unless explicitly told to.

1. **Green first**: run `/verify` (all gates). Do not proceed if anything fails.
2. **E2E** (if requested): build + start the stack
   (`docker compose -f docker-compose.prod.yml -f docker-compose.e2e.yml up -d --build backend
   frontend proxy open-webui`), seed (`scripts/seed_e2e_user.py`), then `cd frontend && CI=true
   BASE_URL=http://localhost npx playwright test`.
3. **Bump**: `./bump_version.sh --patch|--minor|--major` (updates VERSION, `backend/app/main.py`,
   `frontend/package.json`, `frontend/src/app/version.ts`, `.env`, and rotates CHANGELOG).
4. **Changelog**: fill the new version section in `CHANGELOG.md` with real Added/Changed/Fixed notes.
5. **Commit** on a branch (Conventional Commits) and **open a PR**; let the user merge to `main` so
   CI deploys. Never take irreversible prod actions without explicit confirmation.

Argument = bump type / release notes: $ARGUMENTS
