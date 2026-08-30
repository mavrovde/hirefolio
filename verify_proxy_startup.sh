#!/bin/bash
set -eo pipefail

echo "========================================"
echo "🛡️  STARTING PROXY SMOKE TEST (PROD ENV) 🛡️"
echo "========================================"

# Use 'latest' to ensure backend/frontend images can be pulled (they exist as latest)
# We will verify our LOCALLY built proxy:latest against them.
# Use environment IMAGE_TAG or default to 'latest'
export IMAGE_TAG="${IMAGE_TAG:-latest}"
unset COMPOSE_FILE
unset COMPOSE_PATH_SEPARATOR
PROXY_IMAGE="maverickde/mavrov.de-proxy:$IMAGE_TAG"
BACKEND_IMAGE="maverickde/mavrov.de-backend:$IMAGE_TAG"
FRONTEND_IMAGE="maverickde/mavrov.de-frontend:$IMAGE_TAG"

cleanup() {
    echo "🧹 Cleaning up..."
    # Stop proxy and the dependencies we might have started
    docker-compose -f docker-compose.prod.yml down || true
}
trap cleanup EXIT

# 1. Build Images Locally (Ensure we test what we just wrote)
echo "[1/4] Building Images ($IMAGE_TAG)..."

# Important: Copy certs into the proxy build context because Dockerfile expects 'COPY certs'
echo "  - Preparing Proxy build context..."
mkdir -p ./proxy/certs
cp certs/mavrov.de.bundle.cer ./proxy/certs/ 2>/dev/null || true
cp certs/mavrov.de.key ./proxy/certs/ 2>/dev/null || true

echo "  - Building Proxy $PROXY_IMAGE..."
docker build -t "$PROXY_IMAGE" ./proxy >/dev/null

echo "  - Building Backend $BACKEND_IMAGE..."
docker build -t "$BACKEND_IMAGE" ./backend >/dev/null

echo "  - Building Frontend $FRONTEND_IMAGE..."
docker build -t "$FRONTEND_IMAGE" ./frontend >/dev/null

# 2. Start Proxy (and dependencies) using Prod Compose
echo "[2/4] Starting Proxy stack (Prod Env)..."
# We start proxy (which triggers deps)
export IMAGE_TAG="$IMAGE_TAG"
docker-compose -f docker-compose.prod.yml up -d --force-recreate proxy

# 3. Wait for Startup
echo "[3/4] Waiting for startup (5s)..."
sleep 5

# 4. Verify Logs
echo "[4/4] Verifying logs..."
LOGS=$(docker-compose -f docker-compose.prod.yml logs proxy 2>&1)

if echo "$LOGS" | grep -q "Starting Nginx in HTTP/HTTPS mode..."; then
    echo "✅ Proxy Log Check: HTTP/HTTPS mode initialized"
else
    echo "❌ Proxy Log Check: HTTP/HTTPS mode log missing"
    echo "$LOGS"
    exit 1
fi

# 5. Active Endpoint Verification (Smoke Test)
echo "[5/5] Verifying endpoints with curl..."

# Helper function to check status code
check_status() {
    local url=$1
    local method=$2
    local expected=$3
    local response
    response=$(curl -s -k -o /dev/null -w "%{http_code}" -X "$method" "$url")

    if [ "$response" -eq "$expected" ]; then
        echo "✅ Endpoint Check: $method $url returned $response (Expected $expected)"
    else
        echo "❌ Endpoint Check: $method $url returned $response (Expected $expected)"
        exit 1
    fi
}

echo "Waiting for backend to be ready (up to 30s)..."
count=0
until curl -s -k -f -o /dev/null "http://localhost/api/app/stats/public" || [ $count -eq 15 ]; do
    echo "  - Backend not ready yet... (Attempt $((count+1))/15)"
    sleep 2
    count=$((count + 1))
done

# Check 1: Public Stats (Existing)
check_status "http://localhost/api/app/stats/public" "GET" "200"

# Check 2: Multi-Chat (New Endpoint) - Expect 405 Method Not Allowed for GET (proving existence)
# or 422 for POST with empty body. Using GET is simpler for existence check.
check_status "http://localhost/api/app/ai/multi-chat" "GET" "405"

# Check 3: Check Posts (Public Endpoint, replaces Tags which is 401)
check_status "http://localhost/api/app/posts" "GET" "200"

# Check 4: Generate Name (Another AI public endpoint, expect 405 Method Not Allowed on GET)
check_status "http://localhost/api/app/ai/generate-name" "GET" "405"

# Check 5: Post display by slug URL (Frontend SSR Routing Test)
check_status "http://localhost/blog" "GET" "200"

# No network connectivity check requested ("do not test something, just successfully start")
# Just confirming that it didn't crash and started up nicely in the prod env topology.

echo "========================================"
echo "✅ PROXY SMOKE TEST PASSED (PROD ENV)"
echo "========================================"
