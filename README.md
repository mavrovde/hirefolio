# mavrov.de

Personal portfolio website with blog functionality powered by semantic search and local AI tag generation.

## 🚀 Features

- **Modern Portfolio**: Showcase experience, skills, education, and recommendations
- **Multilingual**: Full support for English and German with real-time switching
- **Blog with Semantic Search**: AI-powered content discovery using `nomic-embed-text` embeddings
- **AI Tag Generation**: Auto-suggest tags for posts using `tinyllama` model
- **Responsive Design**: Works seamlessly on desktop and mobile
- **Admin Dashboard**: Secure interface for managing posts (rich editor, drafting, publishing)
- **Type-Safe**: Full TypeScript/Python type coverage

## 🏗️ Architecture

### Frontend
- **Framework**: Angular 18+ (Standalone Components, Signals)
- **Styling**: Vanilla CSS (Tailwind concepts), Dark/Light mode
- **State Management**: RxJS Observables
- **Testing**: Vitest (Unit), Playwright (E2E)
- **i18n**: Custom translation service

### Backend
- **Framework**: FastAPI (Python 3.13+)
- **Database**: PostgreSQL 16 with `pgvector` extension
- **AI**: Ollama (Local LLM & Embeddings)
    - Embeddings: `nomic-embed-text`
    - Logic/Text: `tinyllama`
- **ORM**: SQLAlchemy 2.0 (async)
- **Testing**: pytest (High coverage >89%)

### CI/CD Pipeline
- **Platform**: GitHub Actions
- **Quality Gates**:
    - Linting (Ruff, ESLint)
    - Type Checking (MyPy)
    - Security Scanning (Bandit)
    - Unit Tests (Frontend & Backend)
    - E2E Tests (Playwright with real Ollama integration)
- **Optimization**: Aggressive caching for Docker images, AI models, and browsers

## 📋 Prerequisites

- **Node.js** 20+
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

- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Ollama**: http://localhost:11434

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

```
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
│   │   │   ├── components/ # UI components
│   │   │   ├── services/   # Angular services
│   │   │   ├── pipes/      # Custom pipes
│   │   │   └── testing/    # Test utilities
│   │   └── assets/         # Static assets
│   └── package.json        # Node dependencies
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

- **Backend**: >80% coverage (services, API, models)
- **Frontend**: >75% coverage (components, services, pipes)

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

- **Website**: https://mavrov.de
- **LinkedIn**: [Your LinkedIn Profile]
- **Email**: [Your Email]

## 🗺️ Roadmap

- [x] Blog management admin interface
- [x] User authentication and authorization (Admin only)
- [x] AI Tag Suggestions
- [ ] Image upload and management (Next priority)
- [ ] RSS feed generation
- [ ] SEO optimization
- [ ] Analytics dashboard
- [ ] Newsletter integration

---

**Built with ❤️ using Angular, FastAPI, and Ollama**
