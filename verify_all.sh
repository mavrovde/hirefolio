#!/bin/bash
set -e

echo "========================================"
echo "🚀 STARTING FULL VERIFICATION SUITE 🚀"
echo "========================================"

# Ensure DOCKER_HOST is set for Podman
if [ -z "$DOCKER_HOST" ]; then
    PODMAN_SOCKET=$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}' 2>/dev/null || true)
    if [ -n "$PODMAN_SOCKET" ]; then
        export DOCKER_HOST="unix://$PODMAN_SOCKET"
        echo "✅ Set DOCKER_HOST to Podman socket: $DOCKER_HOST"
    fi
fi


# 1. Backend Checks (via Docker to ensure consistent environment)
echo ""
echo "backend: 🐍 Running Static Analysis & Tests..."
# Start DB if not running
# Start DB with DEV config to ensure ports are exposed
docker-compose -f docker-compose.yml up -d --force-recreate db
# Run checks
cd backend
/Users/sergii.mavrov/miniconda3/envs/workspace/bin/python3 -m pytest tests
cd ..

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
docker-compose up -d --build backend frontend proxy open-webui
# Waiting for Health with timeouts instead of fixed sleeps
echo "Waiting for Backend to be ready..."
# Portable wait function
count=0
until curl -s -f http://localhost:8000/api/app/health > /dev/null || [ $count -eq 30 ]; do
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
until curl -s -f http://localhost:4200 > /dev/null || [ $count -eq 60 ]; do
    sleep 1
    count=$((count + 1))
    if [ $((count % 10)) -eq 0 ]; then
        echo "Still waiting for Frontend... ($count/60)"
        docker-compose logs --tail=10 proxy frontend
    fi
done

echo "Waiting for Open WebUI to be ready..."
count=0
# Wait longer for Open WebUI (can be slow)
until curl -s -f http://localhost:4200/open/health > /dev/null || [ $count -eq 90 ]; do
    sleep 2
    count=$((count + 1))
    if [ $((count % 5)) -eq 0 ]; then
        echo "Still waiting for Open WebUI... ($((count * 2))/180s)"
    fi
done

if [ $count -eq 90 ]; then
    echo "❌ Open WebUI failed to start on http://localhost:4200/open/health"
    docker-compose ps
    docker-compose logs --tail=20 open-webui
    # We don't exit here, we let the python script fail with more details if needed, or exit?
    # Better to exit to save time.
    exit 1
fi

if [ $count -eq 60 ]; then
    echo "❌ Frontend failed to start on http://localhost:4200"
    docker-compose ps
    docker-compose logs proxy frontend
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
