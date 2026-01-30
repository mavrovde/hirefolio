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
docker-compose run --rm --build -e PIP_ROOT_USER_ACTION=ignore backend bash -c "
    echo 'Installing Dev Dependencies...' && pip install -r requirements-dev.txt && \
    echo 'Running Lint...' && ruff check . && \
    echo 'Running Format Check...' && ruff format . --check && \
    echo 'Running Type Check...' && mypy app --ignore-missing-imports --no-error-summary && \
    echo 'Running Security Check...' && bandit -r app -ll --skip B101 && \
    echo 'Running Tests...' && pytest -p no:warnings --cov=app --cov-report=term-missing
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
docker-compose up -d --build backend frontend proxy
# Wait for health with timeouts instead of fixed sleeps
echo "Waiting for Backend to be ready..."
# Portable wait function
count=0
until curl -s http://localhost:8000/api/health > /dev/null || [ $count -eq 30 ]; do
    sleep 1
    count=$((count + 1))
done

if [ $count -eq 30 ]; then
    echo "Backend failed to start"
    exit 1
fi

echo "🔄 Restarting Frontend & Proxy to ensure fresh DNS resolution..."
docker-compose restart frontend proxy

echo "Waiting for Frontend to be ready..."
count=0
until curl -s http://localhost:4200 > /dev/null || [ $count -eq 60 ]; do
    sleep 1
    count=$((count + 1))
done

if [ $count -eq 60 ]; then
    echo "Frontend failed to start"
    exit 1
fi

echo "🌱 Seeding E2E data..."
docker-compose exec -T backend python scripts/seed_e2e_user.py

# Run Playwright
echo "🛡️  Verifying Proxy Routes..."
python3 -m pip install httpx --quiet --break-system-packages || true
python3 verify_proxy_routes.py

echo "Running Playwright..."
cd frontend
export BASE_URL=http://localhost:4200
CI=true npx playwright test
cd ..

echo ""
echo "========================================"
echo "✅ ALL CHECKS PASSED SUCCESSFULLY! ✅"
echo "========================================"
