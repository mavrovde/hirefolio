# Deployment

Two paths: a **first deploy** onto a clean host (manual, one-time) and the
**automated rollout** that keeps the host current on every green `main` pipeline
once the owner adds three secrets. CI publishes multi-tagged amd64 images to
`ghcr.io/mavrovde/hirefolio-{backend,frontend,admin-frontend,proxy}` —
`sha-<gitsha>`, the release version (e.g. `1.8.4`), and `latest`. The packages
are **public**: any host can `docker compose pull` them with no registry login.

## First deploy (clean server)

Prerequisites on the host: Docker Engine + the compose plugin, ports 80/443
open, DNS for the public + admin hostnames pointed at the host. A panel such as
1Panel may own SSL/certs, or you can mount your own certs (the proxy expects
`fullchain.pem`/`privkey.pem` — see `proxy/`).

```bash
# 1. Get the compose project onto the host (default rollout dir; override with
#    the DEPLOY_DIR secret if you choose another path)
git clone https://github.com/mavrovde/hirefolio.git /opt/mavrov.de
cd /opt/mavrov.de

# 2. Configure — copy the template and fill EVERY required value
cp .env.example .env
#    Required: ADMIN_PASSWORD and JWT_SECRET_KEY (the backend refuses to start
#    without BOTH — generate the JWT secret with `openssl rand -hex 32`, #177),
#    POSTGRES_PASSWORD, LINKEDIN_IMPORT_TOKEN (for the posts importer),
#    PUBLIC_SERVER_NAME / ADMIN_SERVER_NAME, ADMIN_ALLOWED_CIDRS (keep empty =
#    loopback-only admin until you add your operator IPs).
#    Optional: GEMINI_API_KEY (+ GEMINI_ENCRYPTION_KEY) — without it the AI
#    features fall back to the in-stack Ollama.
#    Image coordinates: IMAGE_REPO defaults to ghcr.io/mavrovde/hirefolio;
#    set IMAGE_TAG to the release you are deploying (e.g. 1.8.4).

# 3. Pull the validated images and start (never use `down -v` — volumes hold
#    the database and models)
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# 4. Verify
curl -s https://<public-host>/api/app/health          # -> healthy
curl -s https://<public-host>/api/app/stats/public    # backend_version == IMAGE_TAG
curl -s -o /dev/null -w '%{http_code}' https://<public-host>/admin/login  # -> 404 (freshness probe)
```

The backend runs `alembic upgrade head` on start (schema is created on first
boot) and seeds the admin user from `ADMIN_PASSWORD`. Ollama pulls its models on
first use; the first AI request is slow.

### First content import (LinkedIn posts)

From your workstation (scraper session + data live there, see
`scraper/WORKFLOW.md` and `importer/README.md`):

```bash
cd scraper && PLAYWRIGHT_CHANNEL=chrome node scrape-posts.js   # refresh posts_data.json
cd .. && MAVROV_API_URL=https://<public-host> \
  LINKEDIN_IMPORT_TOKEN=<same value as the host .env> \
  IMPORT_PUBLISH=true python -m importer                        # publish on first import
```

`IMPORT_PUBLISH=true` publishes newly created posts immediately; re-imports
update content but never flip an existing post's published state.

## Automated rollout (the `deploy` job)

`deploy.yml` ends with a `deploy` job that is a **no-op until secrets exist** —
add these in Settings → Secrets and variables → Actions:

| Secret | Required | Meaning |
|---|---|---|
| `DEPLOY_HOST` | yes | Host to SSH to |
| `DEPLOY_USER` | yes | Dedicated non-root deploy user |
| `DEPLOY_SSH_KEY` | yes | Private key for that user (generate a dedicated pair; never reuse a personal key) |
| `DEPLOY_DIR` | no | Compose project dir (default `/opt/mavrov.de`) |
| `DEPLOY_SSH_PORT` | no | SSH port (default 22) |
| `DEPLOY_PUBLIC_URL` | no | Public URL for the health gate (default `https://mavrov.de`) |

On every green pipeline the job then: rewrites only `IMAGE_REPO`/`IMAGE_TAG`
in the host `.env`, deploying the **immutable `sha-<gitsha>` tag** (never the
mutable version tag — that would make rollback a no-op); `.env.rollback`
records only the previous coordinate lines, never secrets. It pulls and
recreates **only the four app services** (`backend frontend admin-frontend
proxy`, `--no-deps`) so the DB/Ollama/Open-WebUI images and volumes are never
rolled by CI, verifies each running container **by image digest**, waits on
`/api/app/health`, runs the retried freshness probe (`/admin/login` → 404,
issue #169), and **rolls back to the previous sha tag** on failure. Volumes
are never touched (CLAUDE.md rule 9).

Host-side hardening checklist: dedicated `deploy` user in the `docker` group
only, `authorized_keys` restricted to that key, password auth off, fail2ban or
an IP allowlist on sshd. The key in GitHub should exist nowhere else.

## Registry notes

- The GHCR packages are public — keep them that way or the host needs a
  read-only PAT `docker login`.
- `build_amd64_and_push.sh` remains as a manual fallback for pushing images
  from a workstation.
