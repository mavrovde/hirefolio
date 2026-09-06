# Deployment

Two paths: a **first deploy** onto a clean host (manual, one-time) and the
**automated rollout** that keeps the host current on every green `main` pipeline
once the owner adds three secrets. CI publishes multi-tagged amd64 images to
`ghcr.io/mavrovde/hirefolio-{backend,frontend,admin-frontend,proxy}` —
`sha-<gitsha>`, the release version (e.g. `1.9.0`), and `latest`. The host pulls
with **no registry login**, so those four packages **must be public** — the four
post-rename `hirefolio-*` packages were created *private* by GitHub and need a
one-time visibility change (see "One-time action after the rename" below).

The same workflow also runs on **pull requests**, but in verification-only mode
(#208): the lint / type / security / unit-test / migration / version gates run,
while every job that builds, publishes, or rolls out is gated on
`github.event_name == 'push'` — nothing is ever published or deployed from a PR.

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
#    Optional: HIREFOLIO_GEMINI_API_KEY (+ HIREFOLIO_GEMINI_ENCRYPTION_KEY) — without it the AI
#    features fall back to the in-stack Ollama.
#    Identity (#65/#66 — the committed DEFAULTS are the Jane Doe demo persona):
#    set SITE_URL, SITE_NAME, OWNER_NAME, OWNER_HEADLINE, OWNER_DESCRIPTION,
#    SOCIAL_LINKS (and HIREFOLIO_ANALYTICS_ID to keep analytics) or the site
#    renders the demo identity and SSR advertises example.com og:url/canonical.
#    Then upload the real Profile Data JSON + CV via the admin panel.
#    Image coordinates: IMAGE_REPO defaults to ghcr.io/mavrovde/hirefolio;
#    set IMAGE_TAG to the release you are deploying (e.g. 1.9.0).

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
| `DEPLOY_PUBLIC_URL` | no | Legacy secret for the health-gate URL — superseded by the `PUBLIC_URL` **variable** below, still honoured |

And one repository **variable** (Settings → Secrets and variables → Actions → Variables):

| Variable | Required | Meaning |
|---|---|---|
| `PUBLIC_URL` | forks: yes | The live site's public URL. ONE knob shared by the deploy gate and the scheduled **Live Freshness** workflow (`.github/workflows/live-freshness.yml`, #169) — the secretless daily alarm that goes **red whenever live ≠ released** (version probe + public `/admin/login` → 404), with a distinct "unreachable" verdict for outages. Forks without it skip the workflow instead of probing the canonical site. The verdict logic lives in `scripts/check_live_freshness.sh`, shared by both callers. Note: GitHub auto-disables scheduled workflows after ~60 days of repo inactivity — re-enable it if the repo goes quiet. |

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

## Upgrading a host across the #141 rename

The Gemini variables are project-scoped since #141. Before rolling out a release that contains it,
rename them in the host `.env`:

```diff
-GEMINI_API_KEY=...
-GEMINI_ENCRYPTION_KEY=...
+HIREFOLIO_GEMINI_API_KEY=...
+HIREFOLIO_GEMINI_ENCRYPTION_KEY=...
```

Leaving the old names is **not** fatal — the app ignores them, AI features fall back to the in-stack
Ollama, and the backend prints a `CONFIG WARNING` naming each stale variable at startup (the compose
files pass the legacy *names*, never their values, so nothing sensitive enters the container).
`GEMINI_MODEL`/`GEMINI_MODEL_FALLBACK` follow the same rule; they are namespaced because model choice
is a cost control.

If a host had `GEMINI_ENCRYPTION_KEY` set and rows already encrypted (`enc:v1:` prefix), renaming
without carrying the value over makes those values read as unset — recoverable by setting
`HIREFOLIO_GEMINI_ENCRYPTION_KEY` to the same key.

Apply it with `docker compose -f docker-compose.prod.yml up -d backend`, **not** `restart`: compose
resolves the environment when it *creates* a container, so `restart` reuses the old values and the
edit appears to have done nothing. Then verify the container actually sees the new names:

```bash
docker compose -f docker-compose.prod.yml exec backend env | grep GEMINI
# expect HIREFOLIO_GEMINI_*; a bare GEMINI_API_KEY here means the rename did not take
docker compose -f docker-compose.prod.yml logs backend | grep 'CONFIG WARNING'
# any line names a variable still set under its old name on the host
```

## Registry notes

- **One-time action after the rename to `hirefolio` (#88/#189):** CI publishes to
  `ghcr.io/<owner>/<repo>-*`, so the first build after the rename creates four
  **brand-new** GHCR packages — `hirefolio-backend`, `hirefolio-frontend`,
  `hirefolio-admin-frontend`, `hirefolio-proxy`. New packages default to
  **private**, and package visibility does **not** follow a repository rename.
  The prod host pulls with **no `docker login`**, so make all four public once:
  GitHub → your profile → **Packages** → each package → *Package settings* →
  *Change visibility* → **Public**. The rollout job preflights this and fails
  with an explicit message naming the package if it is still private, before it
  touches the host.
- Images published **before** the rename remain at `ghcr.io/mavrovde/mavrov.de-*`
  (still public). To deploy a pre-rename tag such as `1.8.4`, pin
  `IMAGE_REPO=ghcr.io/mavrovde/mavrov.de` explicitly.
- Once made public, keep them public — otherwise every host needs a read-only
  PAT `docker login` and the rollout job's anonymous-pull preflight fails.
- `build_amd64_and_push.sh` remains as a manual fallback for pushing images
  from a workstation.
