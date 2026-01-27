#!/bin/bash
set -e

echo "========================================"
echo "🛡️  STARTING PROXY SMOKE TEST (PROD ENV) 🛡️"
echo "========================================"

# Use 'latest' to ensure backend/frontend images can be pulled (they exist as latest)
# We will verify our LOCALLY built proxy:latest against them.
# Use environment IMAGE_TAG or default to 'latest'
export IMAGE_TAG="${IMAGE_TAG:-latest}"
PROXY_IMAGE="ghcr.io/mavrovde/mavrov.de-proxy:$IMAGE_TAG"
BACKEND_IMAGE="ghcr.io/mavrovde/mavrov.de-backend:$IMAGE_TAG"
FRONTEND_IMAGE="ghcr.io/mavrovde/mavrov.de-frontend:$IMAGE_TAG"

cleanup() {
    echo "🧹 Cleaning up..."
    # Stop proxy and the dependencies we might have started
    docker-compose -f docker-compose.prod.yml down
}
trap cleanup EXIT

# 1. Build Images Locally (Ensure we test what we just wrote)
echo "[1/4] Building Images ($IMAGE_TAG)..."

# Important: Copy certs into the proxy build context because Dockerfile expects 'COPY certs'
echo "  - Preparing Proxy build context..."
mkdir -p ./proxy/certs
cp certs/mavrov.de.bundle.cer ./proxy/certs/
cp certs/mavrov.de.key ./proxy/certs/

echo "  - Building Proxy $PROXY_IMAGE..."
docker build -t "$PROXY_IMAGE" ./proxy >/dev/null

echo "  - Building Backend $BACKEND_IMAGE..."
docker build -t "$BACKEND_IMAGE" ./backend >/dev/null

echo "  - Building Frontend $FRONTEND_IMAGE..."
docker build -t "$FRONTEND_IMAGE" ./frontend >/dev/null

# 2. Start Proxy (and dependencies) using Prod Compose
echo "[2/4] Starting Proxy stack (Prod Env)..."
# We start proxy (which triggers deps)
docker-compose -f docker-compose.prod.yml up -d proxy

# 3. Wait for Startup
echo "[3/4] Waiting for startup (5s)..."
sleep 5

# 4. Verify Logs
echo "[4/4] Verifying logs..."
LOGS=$(docker-compose -f docker-compose.prod.yml logs proxy 2>&1)

if echo "$LOGS" | grep -q "Starting Nginx in static SSL mode..."; then
    echo "✅ Proxy Log Check: Static SSL mode initialized"
else
    echo "❌ Proxy Log Check: Static SSL mode log missing"
    echo "$LOGS"
    exit 1
fi

if echo "$LOGS" | grep -q "Starting Nginx..."; then
    echo "✅ Proxy Log Check: Nginx started"
else
    echo "❌ Proxy Log Check: Nginx start log missing"
    echo "$LOGS"
    exit 1
fi

# No network connectivity check requested ("do not test something, just successfully start")
# Just confirming that it didn't crash and started up nicely in the prod env topology.

echo "========================================"
echo "✅ PROXY SMOKE TEST PASSED (PROD ENV)"
echo "========================================"
