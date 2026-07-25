# mavrov.de

Personal portfolio website with blog functionality powered by semantic search and local AI tag generation.

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

- **Framework**: Angular 21 (Standalone Components, Signals, Native SSR `server.mjs`)
- **Styling**: TailwindCSS 4.x, Dark/Light mode
- **State Management**: RxJS 7.8 Observables
- **Testing**: Vitest 4.0 (Unit, replaced Jasmine/Karma), Playwright 1.58 (E2E)
- **i18n**: Custom translation service

### Backend

- **Framework**: FastAPI 0.129 (Python 3.13+)
- **Database**: PostgreSQL 16 with `pgvector` extension
- **AI**: Ollama (Local LLM & Embeddings)
  - Embeddings: `nomic-embed-text`
  - Chat/generation: `llama3.2`
  - Fast metadata/tags: `llama3.2:1b`
- **ORM**: SQLAlchemy 2.0.46 (async)
- **Testing**: pytest + Vitest (100% line & branch coverage)

### CI/CD Pipeline

- **Platform**: GitHub Actions
- **Quality Gates**:
  - Linting (Ruff 0.15, ESLint)
  - Type Checking (MyPy)
  - Security Scanning (Bandit)
  - Unit Tests (Frontend & Backend)
  - E2E Tests (Playwright with real Ollama integration)
- **Optimization**: Aggressive caching for Docker images, AI models, and browsers

## 📋 Prerequisites

- **Node.js** 20+ (npm 11+)
- **Python** 3.13+
- **PostgreSQL** 16+
- **Docker/Podman** (Recommended for local dev)
- **Ollama** (If running locally without Docker)

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd mavrov.de
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
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

### 2. End-to-End (E2E)

Our E2E suite runs in a fully isolated testing environment (with dedicated DB and AI models).

```bash
cd frontend
npx playwright test
```

### 3. Verification Script

Run the entire test suite (Lint, Type Check, Unit, E2E) in one go:

```bash
./verify_all.sh
```

## 📁 Project Structure

```text
mavrov.de/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── models/         # Database models
│   │   ├── services/       # Business logic
│   │   ├── config.py       # Configuration
│   │   ├── database.py     # Database setup
│   │   └── main.py         # FastAPI app
│   ├── tests/              # Backend tests
│   ├── scripts/            # Utility scripts
│   └── requirements.txt    # Python dependencies
├── frontend/               # Angular frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/ # UI components (e.g., Header, HomeComponent, CV)
│   │   │   ├── services/   # Angular services (SEO, API, State)
│   │   │   ├── pipes/      # Custom pipes
│   │   │   └── testing/    # Test utilities
│   │   ├── environments/   # Configuration for Dev/Prod APIs
│   │   └── server.ts       # Angular Universal SSR server handler
├── scraper/                # LinkedIn profile scraper
├── docker-compose.yml      # Service orchestration
└── README.md              # This file
```

## 🔧 Configuration

### Backend Environment Variables

Create `backend/.env`:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mavrov
OLLAMA_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
GEMINI_API_KEY=your_api_key_here

# LinkedIn import (optional — leave blank to disable the import endpoint)
LINKEDIN_IMPORT_TOKEN=your_machine_token_here   # default: "" (disabled)
IMPORT_MAX_IMAGE_MB=10                          # default: 10 MB
```

### Root Environment (Release Script)

Create `.env` in the project root to configure the release script:

```bash
GEMINI_API_KEY=your_api_key_here
```

### Frontend Environment

Edit `frontend/src/environments/environment.ts`:

```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
  googleAnalyticsId: 'G-XXXXXXXXXX'
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
| `68db39a6f58e` | Add `image_url` to posts (initial) |
| `d45b3e9ce716` | Add `image_blob` + `image_type` to posts |
| `c3f8a1d2e947` | Add LinkedIn provenance columns (`source_urn`, `source_url`, `posted_at`) |

### Health Check

- `GET /` - Welcome message
- `GET /api/health` - Health status

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

### Production Build

```bash
# Frontend
cd frontend
npm run build
# Output: dist/

# Backend
cd backend
# Already production-ready with FastAPI
```

### Docker Production

```bash
# Build and start all services
docker-compose up -d --build

# Scale backend (if needed)
docker-compose up -d --scale backend=3
```

## 🛠️ Development

### Hot Reload

- **Frontend**: Automatic with `ng serve`
- **Backend**: Use `uvicorn app.main:app --reload`

### Code Quality

```bash
# Frontend linting
cd frontend
npm run lint

# Backend formatting
cd backend
black app/
isort app/
```

## 📊 Test Coverage

- **Backend**: ~99% line & branch coverage (652 tests)
- **Frontend**: 100% coverage across statements, branches, functions & lines (687 tests)
- **E2E**: 81 Playwright tests passing against the full stack (real Ollama integration)

Run coverage reports:

```bash
# Backend
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Frontend
npm test -- --coverage
open coverage/index.html
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

---

**Built with ❤️ using Angular, FastAPI, and Ollama**
