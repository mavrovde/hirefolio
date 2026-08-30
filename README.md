# Hirefolio

**A fork-and-go, self-hostable portfolio + recruiter-communication platform for job-seeking software
engineers** — semantic blog search, local-AI tagging, and an admin console, deployable under *your*
own name and domain.

> **Name change (#88):** the project is now **Hirefolio** and the repository is
> [`mavrovde/hirefolio`](https://github.com/mavrovde/hirefolio) (GitHub redirects the old
> `mavrovde/mavrov.de` URLs, and `git remote` keeps working — but update your remote when convenient:
> `git remote set-url origin https://github.com/mavrovde/hirefolio.git`).
> `mavrov.de` remains the maintainer's own deployment of it, not the product name.
> Container images publish to `ghcr.io/mavrovde/hirefolio-*` from the first build after the rename;
> images published earlier still live at `ghcr.io/mavrovde/mavrov.de-*`, so pin `IMAGE_REPO`
> explicitly when deploying a pre-rename tag. **One-time owner action:** those four new GHCR
> packages are created **private** (visibility does not follow a repo rename) — make them public
> once, or the host, which pulls without a login, cannot fetch them. See
> [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md#registry-notes).

## 🚀 Features

- **Modern Portfolio**: Showcase experience, skills, education, and recommendations
- **Multilingual**: Full support for English and German with real-time switching
- **Blog with Semantic Search**: AI-powered content discovery using `nomic-embed-text` embeddings
- **AI Tag Generation**: Auto-suggest tags for posts using a local `llama3.2:1b` model
- **Responsive Design**: Works seamlessly on desktop and mobile
- **Admin Dashboard**: Secure interface for managing posts (rich editor, drafting, publishing)
- **Type-Safe**: Full TypeScript/Python type coverage

## 🏗️ Architecture

### Frontend

- **Framework**: Angular 22 (Standalone Components, RxJS + `async` pipe for state — Signals only for local component state, Native SSR `server.mjs`)
- **Styling**: TailwindCSS 4.x, Dark/Light mode
- **State Management**: RxJS 7.8 Observables
- **Testing**: Vitest 4.1 (Unit, replaced Jasmine/Karma), Playwright 1.62 (E2E)
- **i18n**: Custom translation service

### Backend

- **Framework**: FastAPI 0.141 (Python 3.12 — the version the Docker images and CI run)
- **Database**: PostgreSQL 16 with `pgvector` extension
- **AI**: Ollama (Local LLM & Embeddings)
  - Embeddings: `nomic-embed-text`
  - Chat/generation: `llama3.2`
  - Fast metadata/tags: `llama3.2:1b`
- **ORM**: SQLAlchemy 2.0.52 (async)
- **Testing**: pytest + Vitest (100% line & branch coverage)

### CI/CD Pipeline

- **Platform**: GitHub Actions
- **Quality Gates**:
  - Linting (Ruff 0.16 for the backend; no frontend linter is configured — the CI
    frontend-lint job runs `npm run lint --if-present`, which is currently a no-op)
  - Type Checking (MyPy)
  - Security Scanning (Bandit)
  - Unit Tests (Frontend & Backend)
  - E2E Tests (Playwright with real Ollama integration)
- **Optimization**: Playwright-browser caching in CI — deliberately **no** multi-GB caches for Docker base images or AI model weights (measured net-negative; see `.claude/skills/lessons-learned/SKILL.md` §5)

## 📋 Prerequisites

- **Node.js** 22 (what CI uses; npm 10+)
- **Python** 3.12 (what the Docker images and CI use; a newer local venv may work but is not the reference)
- **PostgreSQL** 16+
- **Docker/Podman** (Recommended for local dev)
- **Ollama** (If running locally without Docker)

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd hirefolio
```

### 2. Start Everything (Docker)

The easiest way to run the full stack (Frontend, Backend, DB, Ollama):

```bash
# Start all services
./manage.sh start

# View logs
./manage.sh logs

# Stop services
./manage.sh stop
```

### 3. Manual Setup (Local Dev)

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start DB (using Docker is easiest for PGVector)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg16

# Run Migrations
alembic upgrade head

# Start Server
uvicorn app.main:app --reload
```

> **Alembic is the single, authoritative schema-management mechanism** — the backend no longer
> calls `Base.metadata.create_all` at startup. Docker images run `alembic upgrade head` via
> `backend/docker-entrypoint.sh` before the app starts (idempotent — a no-op once the DB is at
> head); running it manually is only needed for local dev outside Docker. See
> [`backend/migrations/`](./backend/migrations/) and
> [How to write a migration](#how-to-write-a-migration) below.

#### How to write a migration

```bash
cd backend
# 1. Change a model in app/models/*.py
# 2. Generate a migration from the diff (review it — autogenerate misses some things,
#    e.g. data backfills, column renames it sees as drop+add, and check constraints):
alembic revision --autogenerate -m "describe the change"
# 3. Apply it locally and confirm it's the diff you expect:
alembic upgrade head
# 4. Guard against drift — this must report "No new upgrade operations detected.":
alembic check
```

A non-additive change (column type change, `NOT NULL` backfill, rename, new constraint) goes
through the same `alembic revision --autogenerate` + hand-edit workflow — Alembic (unlike
`create_all`) can express and apply these safely.

#### Frontend

```bash
cd frontend
npm install
npm start
```

### 5. Access Application

- **Frontend**: <http://localhost:4200>
- **Backend API**: <http://localhost:8000>
- **API Docs**: <http://localhost:8000/docs>
- **Ollama**: <http://localhost:11434>

## 🤖 AI Assistant (Claude Code)

**Claude Code is the primary AI tool for this project.** All assistant guidance lives in
[`CLAUDE.md`](./CLAUDE.md) (stack facts, commands, the LinkedIn pipeline, engineering rules, and the
configured MCP servers / subagents / plugins / slash commands). Legacy per-tool files
(`.cursorrules`, `.windsurfrules`, `.cline.md`, `.geminirules`, `AI.md`, `.clauderules`) are thin
pointers to `CLAUDE.md`.

Project-scoped Claude Code tooling: subagents under `.claude/agents/` (`devops-pipeline`,
`backend-dev`, `frontend-dev`), slash commands under `.claude/commands/` (`/verify`, `/release`,
`/linkedin-sync`), and the plugins listed in `CLAUDE.md`.

### MCP Servers

A project-scoped `.mcp.json` configures Model Context Protocol servers to speed up development with Claude Code. On first use, Claude Code will ask you to approve the project's MCP servers.

| Server | Purpose | Requirements |
| --- | --- | --- |
| `postgres` | Read-only SQL queries against the `pgvector` database (inspect posts, embeddings, CV data) | DB running on `127.0.0.1:5433`; override URL via `MCP_POSTGRES_URL` |
| `playwright` | Drive a real browser for interactive UI debugging / E2E authoring | none (browser auto-installed) |
| `github` | Manage PRs, issues and Dependabot alerts | export `GITHUB_PERSONAL_ACCESS_TOKEN` (never committed) |

```bash
# Optional overrides before launching Claude Code
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxx        # for the github server
export MCP_POSTGRES_URL=postgresql://user:pass@host:5433/mavrov  # non-default DB
```

Secrets are supplied only via environment variables — `.mcp.json` contains no credentials.

## 🧪 Testing

We verify the application at multiple levels:

### 1. Unit & Integration

```bash
# Backend (needs Postgres on 127.0.0.1:5433; point TEST_DATABASE_URL at a test_* DB —
# see README_TESTING.md for the isolation rules)
cd backend && pytest

# Frontend (all three workspace projects: shared, public, admin)
cd frontend && npm test
```

### 2. End-to-End (E2E)

**Prerequisite:** the E2E suite runs against a live stack — start it first
(`./manage.sh start`, or the dedicated compose E2E stack that `./verify_all.sh` uses).

```bash
cd frontend
npx playwright test                        # both suites
npx playwright test --project=public-e2e   # public app only
npx playwright test --project=admin-e2e    # admin app only
```

### 3. Verification Script

Run the entire test suite (Lint, Type Check, Unit, E2E) in one go:

```bash
./verify_all.sh
```

## 📁 Project Structure

```text
hirefolio/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/                 # API endpoints
│   │   ├── models/              # Database models
│   │   ├── services/            # Business logic
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # Database setup
│   │   └── main.py              # FastAPI app
│   ├── migrations/              # Alembic migrations (the schema authority)
│   ├── tests/                   # Backend tests
│   ├── scripts/                 # Utility scripts (incl. create_test_db.py)
│   └── requirements.txt         # Python dependencies
├── frontend/                    # Angular 22 workspace (3 projects)
│   ├── projects/
│   │   ├── public/              # Visitor app — native SSR (src/server.ts), zoneless
│   │   ├── admin/               # Admin console — CSR SPA
│   │   └── shared/              # @mavrov/shared library used by both apps
│   ├── e2e/                     # Playwright suites (public-e2e / admin-e2e)
│   ├── Dockerfile               # public (SSR) image
│   ├── Dockerfile.admin         # admin-frontend image
│   └── playwright.config.ts
├── proxy/                       # Reverse proxy (nginx) config + entrypoint
├── scraper/                     # LinkedIn scrapers (profile + posts → *_data.json)
├── importer/                    # LinkedIn → backend post importer
├── agents/                      # A2A multi-agent delivery team
├── specs/                       # Feature specs (inbox/planned/done)
├── docker-compose.yml           # Dev stack
├── docker-compose.prod.yml      # Prod stack (pulls published images)
└── README.md                    # This file
```

## 🔧 Configuration

### Backend Environment Variables

Create `backend/.env`:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mavrov
OLLAMA_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
GEMINI_API_KEY=your_api_key_here

# Fernet key that encrypts the per-user Gemini API key at rest (issue #143).
# Empty = plaintext passthrough (backward compatible); set in prod to encrypt.
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
GEMINI_ENCRYPTION_KEY=                          # default: "" (encryption disabled)
#
# NOTE (encrypting EXISTING keys): the `encrypt0002` migration runs once at
# deploy. If GEMINI_ENCRYPTION_KEY was still empty when it ran, existing keys
# stay plaintext — setting the key later does NOT retroactively encrypt them.
# After enabling the key, encrypt existing rows by either (a) re-saving the key
# in the admin profile UI, or (b) running the idempotent backfill once:
#   cd backend && GEMINI_ENCRYPTION_KEY=... python -m scripts.backfill_encrypt_gemini_key
# (Regardless of encryption, `/auth/me` never returns the raw key — the network
# EXPOSURE is closed independently of encryption-at-rest.)

# LinkedIn import (optional — leave blank to disable the import endpoint)
LINKEDIN_IMPORT_TOKEN=your_machine_token_here   # default: "" (disabled)
IMPORT_MAX_IMAGE_MB=10                          # default: 10 MB

# Where the saved LinkedIn login session is stored. Defaults to
# /data/linkedin_cookies, backed by the `linkedin_cookies` named volume so the
# session survives container recreates/deploys.
LINKEDIN_COOKIES_DIR=/data/linkedin_cookies    # default: /data/linkedin_cookies
```

### Root Environment (Docker Compose)

Docker Compose auto-loads `.env` from the project root — it configures the
compose stacks (image registry/tag, hostnames, admin allowlist, ports, …).
Copy [`.env.example`](.env.example) to `.env` and adjust; every knob is
documented there and has a safe default.

### Deploying as a new owner (fork & go)

All owner-specific deployment/infra settings are externalized behind env/config — a forker
deploys by editing **only** [`.env`](.env.example) (and, for CI publishing, GitHub repository
variables), never tracked source. Copy [`.env.example`](.env.example) to `.env` and set what
identifies you. Every knob has a safe default that preserves the canonical behavior:

| Knob | Where | Default | What it controls |
| --- | --- | --- | --- |
| `IMAGE_REPO` | `.env` (compose) | `ghcr.io/mavrovde/hirefolio` (prod), `mavrovde` (dev) | Registry/org/name the compose files pull `-backend/-frontend/-admin-frontend/-proxy` images from |
| `IMAGE_TAG` | `.env` (compose) | repo `VERSION` | Pinned image tag to run |
| `REGISTRY`, `IMAGE_NAME` | GitHub **repository variables** | `ghcr.io`, `${{ github.repository }}` | Where `deploy.yml` publishes images (override to retarget the CI publish) |
| `PUBLIC_SERVER_NAME` | `.env` (proxy) | `mavrov.de www.mavrov.de` | Public site hostname(s) the reverse proxy answers on |
| `ADMIN_SERVER_NAME` | `.env` (proxy) | `admin.mavrov.de admin.localhost` | Admin console hostname(s) |
| `ADMIN_ALLOWED_CIDRS` | `.env` (proxy) | *empty → CLOSED (loopback only)* | Trusted operator IPs/CIDRs allowed to reach the admin console. **Never `0.0.0.0/0` in prod.** |
| `TRUSTED_PROXY_CIDRS` | `.env` (proxy) | `172.16.0.0/12` (Docker bridge) | Upstream CIDR(s) nginx trusts for the forwarded-for header (real client IP recovery) |
| `REAL_IP_HEADER` | `.env` (proxy) | `X-Forwarded-For` | Header carrying the real client IP (set `X-Real-IP` if your front proxy uses it) |
| `POSTGRES_PORT` | `.env` (compose) | `5433` | Postgres listen port + host mapping + backend `DATABASE_URL` |

The reverse proxy renders its `server_name` from `PUBLIC_SERVER_NAME`/`ADMIN_SERVER_NAME` at
container start (`proxy/entrypoint.sh` → envsubst on `proxy/default.conf.template`).

**Admin console access (#86).** The admin subdomain ships **CLOSED** to the public. Because Docker
NAT masks every external client to the bridge gateway inside the container, the proxy first uses
nginx `real_ip` to recover the true client IP from the front proxy's forwarded header
(`set_real_ip_from ${TRUSTED_PROXY_CIDRS}` + `real_ip_header ${REAL_IP_HEADER}` +
`real_ip_recursive on`, generated into `proxy/real_ip.conf`), then filters that IP against the
allowlist generated from `ADMIN_ALLOWED_CIDRS` into `proxy/admin_allowlist.conf` (both by
`proxy/generate-admin-config.sh` at start; the committed files are the safe defaults + fallback).
With `ADMIN_ALLOWED_CIDRS` empty only loopback reaches admin; set your operator IPs/CIDRs to open
it. **Prerequisite:** your front proxy must forward the real client IP in `REAL_IP_HEADER` and its
egress must fall inside `TRUSTED_PROXY_CIDRS` — verify the proxy access logs show the real external
client IP (not the gateway) before relying on the allowlist. A fail-safe re-tests the generated
config (`nginx -t`) and falls back to a closed default if it is invalid, so a bad allowlist can
never crash nginx or silently misfilter. **Break-glass** (works even with an empty allowlist): reach
admin over loopback from on the box, e.g. `docker compose exec proxy wget -qO- --no-check-certificate
--header 'Host: admin.<your-domain>' https://127.0.0.1/`, or an SSH tunnel that originates inside the
proxy container. Pinned third-party base images (`pgvector/pgvector:pg16`,
`ollama/ollama:0.5.7`, `ghcr.io/open-webui/open-webui:v0.11.0`) are pinned in one place:
`docker-compose.prod.yml`. CI does **not** cache these multi-GB images — measured net-negative
(see `.claude/skills/lessons-learned/SKILL.md` §5); the E2E job pulls them registry-direct
during `docker compose up`. The **Ollama model weights** (`nomic-embed-text`,
`llama3.2`, `llama3.2:1b`) are pulled by the stack at startup and are deliberately **not** cached
in CI either — multi-GB actions caches restore as slowly as a fresh pull.

### Frontend Environment

Each app has its own environment files:
`frontend/projects/public/src/environments/environment.ts` (+ `.prod.ts`) and
`frontend/projects/admin/src/environments/environment.ts` (+ `.prod.ts`).
For example (public):

```typescript
export const environment = {
  production: false,
  apiUrl: '',
  apiPrefix: '/api/app',
  googleAnalyticsId: 'G-XXXXXXXXXX',
};
```

## 🌐 API Endpoints

### Blog Posts

- `GET /api/posts` - List all posts (with filters)
- `GET /api/posts/{slug}` - Get specific post
- `POST /api/posts` - Create new post
- `PUT /api/posts/{slug}` - Update post
- `DELETE /api/posts/{slug}` - Delete post
- `GET /api/posts/{slug}/similar` - Find similar posts
- `GET /api/posts/search/semantic?q=query` - Semantic search

#### Post model — LinkedIn provenance fields (nullable)

| Column | Type | Constraint | Purpose |
|---|---|---|---|
| `source_urn` | `String` | unique when not null (partial index) | LinkedIn activity URN; enables idempotent imports |
| `source_url` | `String(512)` | — | LinkedIn permalink for the original post |
| `posted_at` | `DateTime(tz=True)` | — | Original publish timestamp from LinkedIn |

All three columns are `NULL` for posts not imported from LinkedIn. Two posts may both have
`source_urn = NULL`; two non-null URNs must be distinct (enforced by
`ix_post_source_urn_unique`).

#### Database migrations

| Revision | Description |
|---|---|
| `baseline0001` | Baseline schema — all current tables (`users`, `cv_documents`, `cv_requests`, `posts` incl. `image_url`/`image_blob`/`image_type` and LinkedIn provenance columns, `profile_snapshots`). Consolidates what used to be several disjoint/incomplete revisions (see #46). |
| `encrypt0002` | Encrypts stored per-user Gemini API keys at rest (Fernet via `GEMINI_ENCRYPTION_KEY`); one-time backfill of existing plaintext keys — a no-op if the key env var is empty when it runs (see #143 and the note in the backend env section above). |

New changes get their own revision on top of this baseline — see
[How to write a migration](#how-to-write-a-migration) above.

### Health Check

- `GET /` - Welcome message
- `GET /api/app/ping` - Liveness (always `200 {"ping": "ok"}` once the process is up)
- `GET /api/app/health` - **Readiness** — `200 {"status": "healthy", "ready": true}` only once the
  schema (Alembic migrations) is present. During the cold-start window where uvicorn is up but
  `alembic upgrade head` (run by `docker-entrypoint.sh`) has not finished, it returns a retryable
  `503 {"status": "initializing", "ready": false}` so orchestrators / the E2E gate wait on true
  readiness instead of racing into a raw `500 UndefinedTableError` (see #124).

## 🤖 Ollama Integration

The application uses Ollama for local, free embeddings:

- **Model**: `nomic-embed-text`
- **Dimensions**: 768
- **Cost**: $0 (completely free)
- **Privacy**: All data stays local
- **Speed**: Fast local inference

### Manual Ollama Commands

```bash
# Check available models
curl http://localhost:11434/api/tags

# Generate embedding
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text",
  "prompt": "Your text here"
}'
```

## 📝 Blog Management

### Create Blog Post

```bash
curl -X POST http://localhost:8000/api/posts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Post",
    "slug": "my-post",
    "content": "Post content...",
    "summary": "Brief summary",
    "language": "en",
    "published": true
  }'
```

### Semantic Search

```bash
curl "http://localhost:8000/api/posts/search/semantic?q=ollama+embeddings&lang=en"
```

## 🚢 Deployment

> **Full runbook:** [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — clean-server first deploy, the
> `DEPLOY_*` secrets that arm the automated rollout, and the required host `.env` values
> (`ADMIN_PASSWORD`, `JWT_SECRET_KEY`).

### What CI publishes

Every merge to `main` runs `.github/workflows/deploy.yml`: after the lint /
type / unit-test / security gates it builds and pushes four images to GitHub
Container Registry (anonymously pullable), then runs the full Docker E2E
against exactly those images:

```text
ghcr.io/mavrovde/hirefolio-backend:sha-<gitsha>
ghcr.io/mavrovde/hirefolio-frontend:sha-<gitsha>
ghcr.io/mavrovde/hirefolio-admin-frontend:sha-<gitsha>
ghcr.io/mavrovde/hirefolio-proxy:sha-<gitsha>
```

After a green E2E each `sha-<gitsha>` image is also promoted to the
`<VERSION>` and `latest` tags. GHCR is the project's registry, and the prod compose
files already default `IMAGE_REPO` to it — override it only when deploying from
a different registry/org (below).

### Rolling out to the host

Since #175 the pipeline ends with a **secrets-gated `Roll Out To Prod Host` job**:
when `DEPLOY_HOST` / `DEPLOY_USER` / `DEPLOY_SSH_KEY` are configured it SSHes to
the host, deploys the immutable `sha-<gitsha>` tag, verifies the containers by
image digest, health-gates `/api/app/health`, freshness-probes `/admin/login`
(→ 404) and rolls back on failure. **Without those secrets it skips and the run
is still green — nothing is rolled out** (the original #112 / #156 gap). See
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). To roll out manually, on the host
set in the root `.env`:

```bash
IMAGE_REPO=ghcr.io/mavrovde/hirefolio
IMAGE_TAG=<version>          # e.g. the current VERSION, or sha-<gitsha>
```

then:

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## 🛠️ Development

### Hot Reload

- **Frontend**: Automatic with `ng serve`
- **Backend**: Use `uvicorn app.main:app --reload`

### Code Quality

```bash
# Backend lint + format + types + security (what CI runs)
cd backend
ruff check .
ruff format --check .        # or `ruff format .` to apply formatting
mypy app --ignore-missing-imports --no-error-summary
bandit -r app -ll --skip B101

# Frontend: no linter is configured (CI's `npm run lint --if-present` is a no-op);
# the type gate is the build itself:
cd frontend
npm run build
```

## 📊 Test Coverage

- **Backend**: 100% line & branch coverage — the maintained project standard
  (engineering rule: never below 95%); `pytest` reports it on every run
- **Frontend**: 100% coverage (statements, branches, functions, lines), maintained
  per workspace project (`shared`, `public`, `admin`)
- **E2E**: Playwright suites (`public-e2e`, `admin-e2e`) against the full Docker stack
  (real Ollama integration)

Run coverage reports:

```bash
# Backend
cd backend
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Frontend (per-project reports under coverage/{shared,public,admin}/)
cd frontend
npm run test:coverage
open coverage/public/index.html
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is private and proprietary.

## 🙏 Acknowledgments

- **Ollama** - Local LLM inference
- **nomic-embed-text** - Free embedding model
- **FastAPI** - Modern Python web framework
- **Angular** - Frontend framework
- **PostgreSQL** - Database with pgvector

## 📞 Contact

- **Website**: <https://mavrov.de>
- **LinkedIn**: [Sergii Mavrov](https://www.linkedin.com/in/smavrov/)
- **Email**: [sergii.mavrov@gmail.com](mailto:sergii.mavrov@gmail.com)

## 🗺️ Roadmap

- [x] Blog management admin interface
- [x] User authentication and authorization (Admin only)
- [x] AI Tag Suggestions (Ollama + Gemini)
- [x] SEO optimization (meta tags, structured data)
- [x] Google Analytics integration
- [x] Gemini AI Chat integration
- [x] CV/Resume management and download
- [x] Admin SQL panel (backup/restore)
- [x] Cookie consent management
- [x] Admin tag manager
- [x] E2E test suite (Playwright)
- [x] RSS feed generation
- [x] Newsletter integration
- [x] Native Angular fragment Anchor Scrolling for SEO Title Tracking
- [x] Automated CD rollout of published images onto the prod host (#175 — activate by adding the `DEPLOY_*` secrets; #112 / #156 close once a real rollout runs)

---

**Built with ❤️ using Angular, FastAPI, and Ollama**
