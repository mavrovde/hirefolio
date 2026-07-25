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
`frontend/projects/public/src/app/version.ts`, `.env` (`IMAGE_TAG`), re-syncs
`frontend/package-lock.json`, and rotates `CHANGELOG.md`. Then `export IMAGE_TAG=$(cat VERSION)`.
Also bump `frontend/projects/shared/package.json` to match.

## 1b. Update prod compose image tags  ⚠️ (bump_version.sh does NOT do this)
`sed` `docker-compose.prod.yml` so `-backend`, `-frontend`, `-admin-frontend`, `-proxy` all use the
new `${IMAGE_TAG:-<VERSION>}` default. **Skipping this leaves prod pulling the previous version's
images** even after a green pipeline — this is a required step.

## 1c. Fill the changelog
Replace the rotated `[<VERSION>]` placeholder with real Added/Changed/Fixed notes.

## 2. Full verification — `./verify_all.sh` (abort on failure, revert the version bump)
Runs: backend `pytest` (Docker DB), frontend per-project `npm run test:coverage` + `npm run build`
(shared → public → admin), then the **Docker E2E stack** (`docker-compose.prod.yml` +
`docker-compose.e2e.yml`, incl. the `admin-frontend` service, seed e2e user, `verify_proxy_routes.py`,
Playwright `public-e2e` + `admin-e2e`). On failure: `git checkout VERSION backend/app/main.py
frontend/package.json frontend/projects/public/src/app/version.ts` and stop.
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

## PR-based release (PREFERRED — used for v1.4.1/1.4.2/1.5.0/1.5.1)
**Default to this over `release.sh`'s direct push to `main`.** Do steps 1–3 (bump + compose tags +
changelog) on a **feature branch**, open a PR, get checks green, and **merge to `main`** — the merge
triggers `deploy.yml`, which runs the same gates + Docker E2E + publishes `<VERSION>`/`latest`. Then
tag `v<VERSION>` on the merge commit (a tag push does not re-trigger the branch pipeline). Still do
**step 1b** (compose tags) and the prod rollout (step 6) — CI publishes images but does not roll the
prod server.

## Security reports (every release)
Before tagging, check GitHub security scanning and triage: `gh api repos/<owner>/<repo>/code-scanning/alerts?state=open`
(CodeQL) and `.../dependabot/alerts?state=open`. Note which are pre-existing vs introduced by the
release; a release is only "confirmed" once the pipeline is green **and** you've reviewed these.
