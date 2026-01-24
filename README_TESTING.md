# Testing Guide

This document explains how to run tests and view coverage reports for the mavrov.de application.

## Backend Tests (Python/FastAPI)

### Prerequisites
- PostgreSQL running (for integration tests)
- Python 3.11+
- Dependencies installed: `pip install -r requirements.txt`

### Running Tests

```bash
cd backend

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_embeddings.py

# Run specific test
pytest tests/test_embeddings.py::test_get_embedding_success

# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Run only unit tests (exclude integration)
pytest tests/ --ignore=tests/integration/

# Run only integration tests
pytest tests/integration/
```

### Coverage Reports

After running tests with coverage, open the HTML report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Test Database

Integration tests use a separate test database (`mavrov_test`). Create it:
```bash
createdb mavrov_test
```

## Frontend Tests (Angular/Vitest)

### Prerequisites
- Node.js 18+
- Dependencies installed: `npm install`

### Running Tests

```bash
cd frontend

# Run all tests
npm test

# Run with coverage
npm test -- --coverage

# Run specific test file
npm test -- header.component.spec.ts

# Run in watch mode
npm test -- --watch

# Run with UI
npm test -- --ui
```

### Coverage Reports

Coverage reports are generated in `coverage/` directory:
```bash
open coverage/index.html  # macOS
xdg-open coverage/index.html  # Linux
```

## Integration Testing with Docker/Podman

### Start Services

> **Note**: These commands work with both Docker and Podman. If using Podman, it has docker-compose compatibility built-in.

```bash
# Start all services (works with both docker-compose and podman-compose)
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Check Ollama is ready
curl http://localhost:11434/api/tags
```

### Create Sample Data

```bash
cd backend
python scripts/create_sample_posts.py
```

### Test API Endpoints

```bash
# List posts
curl http://localhost:8000/api/posts

# Get specific post
curl http://localhost:8000/api/posts/getting-started-ollama

# Semantic search
curl "http://localhost:8000/api/posts/search/semantic?q=ollama+embeddings&lang=en"

# Similar posts
curl http://localhost:8000/api/posts/getting-started-ollama/similar
```

## Manual Testing Checklist

### Backend
- [ ] Ollama service starts and pulls model
- [ ] Database migrations run successfully
- [ ] API endpoints respond correctly
- [ ] Embeddings are generated for new posts
- [ ] Semantic search returns relevant results
- [ ] Similar posts feature works

### Frontend
- [ ] Application loads without errors
- [ ] Language switching works
- [ ] All components render correctly
- [ ] Profile data loads and displays
- [ ] Responsive design works on mobile
- [ ] Analytics tracking initializes

## Coverage Targets

- **Backend**: >80% for services and API endpoints
- **Frontend**: >75% for components and services

## Continuous Integration

For CI/CD pipelines, use:

```bash
# Backend CI
cd backend
pytest --cov=app --cov-report=xml --cov-fail-under=80

# Frontend CI
cd frontend
npm test -- --coverage --run
```

## Troubleshooting

### Backend Tests Fail
- Ensure PostgreSQL is running
- Check test database exists
- Verify Ollama is accessible (for integration tests)

### Frontend Tests Fail
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Check for TypeScript errors: `npm run build`

### Ollama Connection Issues
- Verify Ollama is running: `docker-compose ps`
- Check logs: `docker-compose logs ollama`
- Test endpoint: `curl http://localhost:11434/api/tags`

## Best Practices

1. **Run tests before committing**: Ensure all tests pass
2. **Write tests for new features**: Maintain coverage
3. **Use descriptive test names**: Make failures easy to understand
4. **Mock external dependencies**: Keep tests fast and reliable
5. **Test edge cases**: Handle errors and null values
