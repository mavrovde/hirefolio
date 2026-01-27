#!/bin/bash
set -e

echo "========================================"
echo "🛡️  STARTING PROXY SMOKE TEST (PROD ENV) 🛡️"
echo "========================================"

# Use 'latest' to ensure backend/frontend images can be pulled (they exist as latest)
# We will verify our LOCALLY built proxy:latest against them.
export IMAGE_TAG="latest"
PROXY_IMAGE="ghcr.io/mavrovde/mavrov.de-proxy:$IMAGE_TAG"

cleanup() {
    echo "🧹 Cleaning up..."
    # Stop proxy and the dependencies we might have started
    docker-compose -f docker-compose.prod.yml down
}
trap cleanup EXIT

# 1. Build Proxy Image Locally
echo "[1/4] Building Proxy image ($PROXY_IMAGE)..."
docker build -t "$PROXY_IMAGE" ./proxy >/dev/null

# 2. Start Proxy (and dependencies) using Prod Compose
echo "[2/4] Starting Proxy stack (Prod Env)..."
# We only start 'proxy', but depends_on will pull/start frontend and open-webui
docker-compose -f docker-compose.prod.yml up -d proxy

# 3. Wait for Bootstrap
echo "[3/4] Waiting for bootstrap (10s)..."
sleep 10

# 4. Verify Logs
echo "[4/4] Verifying logs..."
LOGS=$(docker-compose -f docker-compose.prod.yml logs proxy 2>&1)

if echo "$LOGS" | grep -q "Bootstrapping Nginx SSL"; then
    echo "✅ Log Check: Bootstrap started"
else
    echo "❌ Log Check: Bootstrap log missing"
    echo "$LOGS"
    exit 1
fi

if echo "$LOGS" | grep -q "Starting Nginx"; then
    echo "✅ Log Check: Nginx started"
else
    echo "❌ Log Check: Nginx start log missing"
    echo "$LOGS"
    exit 1
fi

# No network connectivity check requested ("do not test something, just successfully start")
# Just confirming that it didn't crash and started up nicely in the prod env topology.

echo "========================================"
echo "✅ PROXY SMOKE TEST PASSED (PROD ENV)"
echo "========================================"
