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
echo "  - Building Proxy $PROXY_IMAGE..."
docker build -t "$PROXY_IMAGE" ./proxy >/dev/null

echo "  - Building Backend $BACKEND_IMAGE..."
docker build -t "$BACKEND_IMAGE" ./backend >/dev/null

echo "  - Building Frontend $FRONTEND_IMAGE..."
docker build -t "$FRONTEND_IMAGE" ./frontend >/dev/null

# 2. Start Proxy AND Certbot (and dependencies) using Prod Compose
echo "[2/4] Starting Proxy & Certbot stack (Prod Env)..."
# We start proxy (which triggers deps) and certbot explicitly
docker-compose -f docker-compose.prod.yml up -d proxy certbot

# 3. Wait for Bootstrap
echo "[3/4] Waiting for bootstrap (10s)..."
sleep 10

# 4. Verify Logs
echo "[4/4] Verifying logs..."
LOGS=$(docker-compose -f docker-compose.prod.yml logs proxy 2>&1)
CERTBOT_LOGS=$(docker-compose -f docker-compose.prod.yml logs certbot 2>&1)

if echo "$LOGS" | grep -q "Bootstrapping Nginx SSL"; then
    echo "✅ Proxy Log Check: Bootstrap started"
else
    echo "❌ Proxy Log Check: Bootstrap log missing"
    echo "$LOGS"
    exit 1
fi

if echo "$LOGS" | grep -q "Starting Nginx"; then
    echo "✅ Proxy Log Check: Nginx started"
else
    echo "❌ Proxy Log Check: Nginx start log missing"
    echo "$LOGS"
    exit 1
fi

# Verify Certbot is trying to request/renew
if echo "$CERTBOT_LOGS" | grep -q "Requesting start certificate..."; then
    echo "✅ Certbot Log Check: Requesting/checking certificate"
elif echo "$CERTBOT_LOGS" | grep -q "renew"; then
     # Might just say it's renewing if the file exists from a previous run (unlikely in clean test but possible)
     echo "✅ Certbot Log Check: Renew/Request logic active"
else
     echo "❌ Certbot Log Check: No activity found"
     echo "$CERTBOT_LOGS"
     exit 1
fi

# No network connectivity check requested ("do not test something, just successfully start")
# Just confirming that it didn't crash and started up nicely in the prod env topology.

echo "========================================"
echo "✅ PROXY SMOKE TEST PASSED (PROD ENV)"
echo "========================================"
