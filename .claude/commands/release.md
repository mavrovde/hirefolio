---
description: Full release runbook — mirrors release.sh end-to-end (bump, compose tags, verify, tag, push, build/publish images)
---

Run a complete, verified release. This command encodes **every action** `release.sh` performs
(read it at `./release.sh`). Argument = bump type + message: `--patch|--minor|--major "<message>"`.
$ARGUMENTS

Never take the irreversible steps (push to `main`, tag push, image publish, prod deploy) without an
explicit green verification and explicit user go-ahead.

## 0. Preconditions (release.sh setup)
- Ensure tooling on PATH: docker/podman, and npm via nvm (`. "$NVM_DIR/nvm.sh"`).
- Load `.env` (exports `GEMINI_API_KEY`, `IMAGE_TAG`, etc.).
- If `DOCKER_HOST` is unset and Podman is used, set it to the Podman socket.
- Require a bump type (`--patch|--minor|--major`) and a **non-empty** release message (fail otherwise).

## 1. Bump version — `./bump_version.sh <bump>`
Updates: `VERSION`, `backend/app/main.py` (`version="…"`), `frontend/package.json`,
`frontend/src/app/version.ts`, `.env` (`IMAGE_TAG`), re-syncs `frontend/package-lock.json`, and
rotates `CHANGELOG.md`. Then `export IMAGE_TAG=$(cat VERSION)`.

## 1b. Update prod compose image tags  ⚠️ (bump_version.sh does NOT do this)
`sed` `docker-compose.prod.yml` so `-backend`, `-frontend`, `-proxy` all use the new
`${IMAGE_TAG:-<VERSION>}` default. **Skipping this leaves prod pulling the previous version's
images** even after a green pipeline — this is a required step.

## 1c. Fill the changelog
Replace the rotated `[<VERSION>]` placeholder with real Added/Changed/Fixed notes.

## 2. Full verification — `./verify_all.sh` (abort on failure, revert the version bump)
Runs: backend `pytest` (Docker DB), frontend `npm run lint`/`npm test --coverage`/`npm run build`,
then the **Docker E2E stack** (`docker-compose.prod.yml` + `docker-compose.e2e.yml`, seed e2e user,
`verify_proxy_routes.py`, Playwright `--grep-invert profile`). On failure: `git checkout VERSION
backend/app/main.py frontend/package.json frontend/src/app/version.ts` and stop.
- ⚠️ `verify_all.sh` line ~26 hardcodes a conda python path (`/Users/sergii.mavrov/...`) — make it
  portable (use `backend/venv` or `python3`) before running on any other machine.

## 2b. Proxy smoke test — `./verify_proxy_startup.sh` (abort + revert on failure)

## 3. Commit — `git add .` then `git commit -m "v<VERSION>: <message>"`

## 4. Tag & push (irreversible)
`git tag -a "v<VERSION>" -m "<message>"` · `git push origin main` · `git push origin "v<VERSION>"`.
Pushing `main` triggers GitHub Actions `deploy.yml` (Prod Deployment): gates → build/publish images
(`cache-from/to: type=gha`) → E2E → deploy.

## 5. Build & publish images — `./build_amd64_and_push.sh`
Builds AMD64 backend/frontend/proxy and pushes them to the registry with the new tag.

## 6. Prod server rollout
`docker compose -f docker-compose.prod.yml up -d` on the prod host pulls the new tagged images
(that's why step 1b matters). Verify the deployed version (e.g. footer `BE: v<VERSION>`).

## Safer PR alternative (used for v1.4.1/1.4.2)
Instead of `release.sh`'s direct push to `main`: do steps 1–3 on a branch, open a PR, and merge to
`main` so CI runs the same gates + E2E + publish. Still do **step 1b** (compose tags) and the prod
server rollout (step 6) — CI publishes images but does not roll the prod server for you.
