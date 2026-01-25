#!/bin/bash
set -e

echo "========================================"
echo "🚀 STARTING FULL VERIFICATION SUITE 🚀"
echo "========================================"

# 1. Backend Checks (via Docker to ensure consistent environment)
echo ""
echo "backend: 🐍 Running Static Analysis & Tests..."
# Start DB if not running
docker-compose up -d db
# Run checks
docker-compose run --rm backend bash -c "
    echo 'Installing Dev Dependencies...' && pip install -r requirements-dev.txt && \
    echo 'Running Lint...' && ruff check . && \
    echo 'Running Type Check...' && mypy app --ignore-missing-imports --no-error-summary && \
    echo 'Running Security Check...' && bandit -r app -ll --skip B101 && \
    echo 'Running Tests...' && pytest --cov=app --cov-report=term-missing
"

# 2. Frontend Checks
echo ""
echo "frontend: 🅰️  Running Lint, Tests & Build..."
cd frontend
echo "Running Lint..."
npm run lint --if-present
echo "Running Tests..."
npm test -- --watch=false --coverage
echo "Building Production..."
npm run build
cd ..

# 3. E2E Checks
echo ""
echo "e2e: 🎭 Running E2E Tests..."
# Ensure full stack is running
echo "Starting full stack..."
docker-compose up -d --build backend frontend
# Wait for health (simple wait for now, ideal would be healthcheck)
echo "Waiting for services to be ready..."
sleep 5
docker-compose restart frontend
sleep 5

echo "🌱 Seeding E2E data..."
docker-compose exec -T backend python scripts/seed_e2e_user.py

# Run Playwright
echo "Running Playwright..."
cd frontend
export BASE_URL=http://localhost:4200
npx playwright test
cd ..

echo ""
echo "========================================"
echo "✅ ALL CHECKS PASSED SUCCESSFULLY! ✅"
echo "========================================"
