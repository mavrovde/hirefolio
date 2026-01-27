#!/bin/bash
set -e

echo "========================================"
echo "🛡️  STARTING PROXY SMOKE TEST 🛡️"
echo "========================================"

NETWORK="proxy-smoke-test-net"
PROXY_CONTAINER="proxy-smoke-test"
FRONTEND_MOCK="frontend-mock"
WEBUI_MOCK="webui-mock"
IMAGE_TAG="mavrovde-proxy:smoke-test"

cleanup() {
    echo "🧹 Cleaning up..."
    docker rm -f $PROXY_CONTAINER $FRONTEND_MOCK $WEBUI_MOCK 2>/dev/null || true
    docker network rm $NETWORK 2>/dev/null || true
}
trap cleanup EXIT

# 1. Setup Network & Mocks
echo "[1/5] Setting up test environment..."
docker network create $NETWORK
echo "      - Starting Mock Frontend..."
docker run -d --name $FRONTEND_MOCK --network $NETWORK --rm nginx:alpine >/dev/null
echo "      - Starting Mock Open WebUI..."
docker run -d --name $WEBUI_MOCK --network $NETWORK --rm nginx:alpine >/dev/null

# 2. Build Proxy
echo "[2/5] Building Proxy image..."
docker build -t $IMAGE_TAG ./proxy >/dev/null

# 3. Run Proxy
echo "[3/5] Starting Proxy container..."
docker run -d --name $PROXY_CONTAINER --network $NETWORK -p 8888:80 --rm $IMAGE_TAG >/dev/null

# 4. Wait for Bootstrap
echo "[4/5] Waiting for bootstrap (10s)..."
sleep 10

# 5. Verify Logs & Connectivity
echo "[5/5] Verifying..."
LOGS=$(docker logs $PROXY_CONTAINER 2>&1)

if ! docker ps | grep -q $PROXY_CONTAINER; then
    echo "❌ Proxy container died!"
    echo "$LOGS"
    exit 1
fi

if echo "$LOGS" | grep -q "Bootstrapping Nginx SSL"; then
    echo "✅ Log Check: Bootstrap started"
else
    echo "❌ Log Check: Bootstrap log missing"
    echo "Logs snippet:"
    echo "$LOGS" | head -n 20
    exit 1
fi

if echo "$LOGS" | grep -q "Starting Nginx"; then
    echo "✅ Log Check: Nginx started"
else
    echo "❌ Log Check: Nginx start log missing"
    echo "$LOGS"
    exit 1
fi

# Check connectivity (expect 301 or 444) on localhost:8888
if curl -v http://localhost:8888 2>&1 | grep -E "301 Moved Permanently|444|200 OK"; then
    echo "✅ Network Check: Proxy is listening and responding"
else
    echo "❌ Network Check: connection failed"
    exit 1
fi

echo "========================================"
echo "✅ PROXY SMOKE TEST PASSED"
echo "========================================"
