---
applyTo: ".github/workflows/**,proxy/**,docker-compose*.yml,backend/Dockerfile*,frontend/Dockerfile*,manage.sh,verify_all.sh,release.sh,bump_version.sh"
---

# Infra / CI / deploy

- `.github/workflows/deploy.yml` is the **prod deploy**: it runs on push to `main` (gates →
  image build/publish → Docker E2E). PRs get CodeQL only. Merging to `main` IS deploying.
- Images are published to **GitHub Container Registry** (`ghcr.io/mavrovde/hirefolio-*` — see
  `REGISTRY`/`IMAGE_NAME` in `deploy.yml`), NOT Docker Hub; do not treat `maverickde/*` Hub
  images as current.
- **Green `deploy.yml` always = images PUBLISHED; live-on-host only if the `deploy` job ran.**
  Since #175 the pipeline ends with a secrets-gated `Roll Out To Prod Host` job (SSH, immutable
  `sha-<gitsha>` tag, digest + health + freshness gates, auto-rollback); with `DEPLOY_HOST`/
  `DEPLOY_USER`/`DEPLOY_SSH_KEY` unset it skips and the run is still green (#112/#156). Check the
  job status; if skipped, verify the live site (footer `BE: vX.Y.Z`) or say rollout is pending.
- CI test stacks must inject **empty/placeholder credentials** (e.g. `GEMINI_API_KEY: ""`) so
  paid APIs fall back to local Ollama. Never wire `${{ secrets.* }}` into a test job — real
  credentials belong only to the production runtime environment.
- Do not add `actions/cache` for multi-GB Docker artifacts (base images, model weights): the
  cache transfer costs as much as re-pulling. Measure real run timings before adding any cache.
- Never weaken a gate to go green: no deleted/skipped tests, lowered thresholds, or removed
  workflow checks.
- Destructive infra commands (`docker volume rm/prune`, `docker compose down -v`,
  `docker system prune`, `rm -rf` of data/volume dirs, DROP of a non-`test_*` DB) require
  explicit user authorization naming the resource. Prefer non-destructive paths (bump the image
  to match the volume schema, migrate, or leave it).
- Proxy: config lives in `proxy/`; admin allowlist + `real_ip` are generated at container start
  from env (`proxy/generate-admin-config.sh`) and ship CLOSED by default. Local proxy HTTPS is
  published on host port 10443.
- Releases: SemVer by content (`### Added` feature → minor; deps/fixes/tooling → patch;
  breaking → major). Tag `vX.Y.Z` only after the pipeline is green; check CodeQL + Dependabot
  every release.
