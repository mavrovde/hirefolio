# mavrov.de

Personal portfolio website with blog functionality powered by semantic search using local AI embeddings.

## 🚀 Features

- **Modern Portfolio**: Showcase experience, skills, education, and recommendations
- **Multilingual**: Full support for English and German
- **Blog with Semantic Search**: AI-powered content discovery using Ollama embeddings
- **Local AI**: Zero-cost embeddings with `nomic-embed-text` model
- **Responsive Design**: Works seamlessly on desktop and mobile
- **Type-Safe**: Full TypeScript/Python type coverage

## 🏗️ Architecture

### Frontend
- **Framework**: Angular 18+ (Standalone Components)
- **Styling**: Vanilla CSS with modern design patterns
- **State Management**: RxJS Observables
- **Testing**: Vitest with comprehensive coverage
- **i18n**: Custom translation service with language switching

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with pgvector extension
- **Embeddings**: Ollama with nomic-embed-text (768 dimensions)
- **ORM**: SQLAlchemy 2.0 (async)
- **Testing**: pytest with >80% coverage

### Infrastructure
- **Containerization**: Docker/Podman with docker-compose
- **Services**: PostgreSQL, Ollama, Backend API
- **Development**: Hot reload for both frontend and backend

## 📋 Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- **PostgreSQL** 16+
- **Docker/Podman** for containerized services
- **Git** for version control

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd mavrov.de
```

### 2. Start Services

```bash
# Start PostgreSQL, Ollama, and Backend
# Start services using the helper script (auto-detects Docker/Podman)
./manage.sh start

# Or restart services cleanly
./manage.sh restart

# Build and start
./manage.sh rebuild

# View logs
./manage.sh logs
```

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create database (if not using Docker)
createdb mavrov

# Run migrations (if needed)
alembic upgrade head

# Create sample blog posts
python scripts/create_sample_posts.py
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

### 5. Access Application

- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Ollama**: http://localhost:11434

## 🧪 Testing

See [README_TESTING.md](README_TESTING.md) for comprehensive testing guide.

### Quick Test Commands

```bash
# Backend tests
cd backend
pytest -v
pytest --cov=app --cov-report=html

# Frontend tests
cd frontend
npm test
npm test -- --coverage
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

- [ ] Blog management admin interface
- [ ] User authentication and authorization
- [ ] Rich text editor for blog posts
- [ ] Image upload and management
- [ ] RSS feed generation
- [ ] SEO optimization
- [ ] Analytics dashboard
- [ ] Newsletter integration

---

**Built with ❤️ using Angular, FastAPI, and Ollama**
