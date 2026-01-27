#!/bin/bash
set -e

echo "========================================"
echo "🛡️  VERIFYING CI FIX LOCALLY (PROD STACK) 🛡️"
echo "========================================"

# 1. Clean up
echo "[1/6] Cleaning up previous containers..."
docker-compose -f docker-compose.prod.yml down -v

# 2. Start Stack (Simulate CI state before seeding)
echo "[2/6] Starting Prod Stack (No Seeding yet)..."
docker-compose -f docker-compose.prod.yml up -d
echo "Waiting 10s for startup..."
sleep 10

# 3. Verify Login FAILS (Expected)
echo "[3/6] Verifying Login FAILS (Expected 401)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:4200/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin")

if [ "$HTTP_CODE" -eq 401 ]; then
    echo "✅ Success: Login failed with 401 as expected (User not seeded yet)."
else
    echo "❌ Failure: Expected 401, got $HTTP_CODE"
    exit 1
fi

# 4. Apply Fix (Seed Database)
echo "[4/6] Applying Fix: Seeding Database..."
docker-compose -f docker-compose.prod.yml exec -T backend python scripts/seed_e2e_user.py

# 5. Verify Login SUCCEEDS (Expected)
echo "[5/6] Verifying Login SUCCEEDS (Expected 200)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:4200/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin")

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Success: Login succeeded with 200 (Fix Verified)."
else
    echo "❌ Failure: Expected 200, got $HTTP_CODE"
    exit 1
fi

# 6. Cleanup
echo "[6/6] Cleanup..."
docker-compose -f docker-compose.prod.yml down -v

echo "========================================"
echo "✅ CI FIX VERIFIED LOCALLY! ✅"
echo "========================================"
