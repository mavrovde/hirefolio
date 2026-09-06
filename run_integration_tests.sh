#!/usr/bin/env bash
# Black-box integration tier (#260): boot the stack with WireMock standing in
# for Ollama, wait for REAL readiness, seed the E2E admin, run the suite,
# tear down containers (NEVER volumes — rule 9).
#
#   ./run_integration_tests.sh            # full cycle
#   KEEP_STACK=1 ./run_integration_tests.sh   # leave the stack up afterwards
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# ABSOLUTE paths: the suite runs from `$ROOT/backend/tests_integration`, and the
# EXIT trap fires from THERE, so relative -f arguments resolved against the test
# directory and the teardown died with "no such file or directory". The script
# then exited 1 after printing "Integration tier PASSED" and left the stack up —
# a green run that reports failure, which is how this tier came to be treated as
# unrunnable and replaced by hand-assembled stacks (#289 review round 1).
COMPOSE=(docker compose -f "$ROOT/docker-compose.yml" -f "$ROOT/docker-compose.inttest.yml")
PYTEST="${PYTEST_PYTHON:-$ROOT/backend/venv/bin/python}"
[ -x "$PYTEST" ] || PYTEST=python3

cd "$ROOT"

cleanup() {
  if [ "${KEEP_STACK:-0}" != "1" ]; then
    echo "==> Stopping containers (volumes untouched)"
    "${COMPOSE[@]}" stop
  else
    echo "==> KEEP_STACK=1 — stack left running"
  fi
}
# Install the trap BEFORE booting: a failed/interrupted `up -d` must still be
# cleaned up (#261 review minor).
trap cleanup EXIT

echo "==> Booting stack (ollama service = WireMock)"
"${COMPOSE[@]}" up -d --no-deps db ollama backend frontend admin-frontend proxy

echo "==> Waiting for real readiness (backend health through its own port)"
count=0
until curl -s -f http://localhost:8000/api/app/health >/dev/null; do
  count=$((count + 1))
  [ "$count" -ge 60 ] && { echo "FATAL: backend never became healthy"; "${COMPOSE[@]}" logs --tail 50 backend; exit 1; }
  sleep 3
done

echo "==> Waiting for WireMock admin API"
count=0
until curl -s -f http://localhost:11434/__admin/health >/dev/null; do
  count=$((count + 1))
  [ "$count" -ge 20 ] && { echo "FATAL: WireMock never became healthy"; exit 1; }
  sleep 2
done

echo "==> Seeding the integration admin user"
"${COMPOSE[@]}" exec -T backend python scripts/seed_e2e_user.py

echo "==> Running the black-box suite"
cd "$ROOT/backend/tests_integration"
"$PYTEST" -m pytest . "$@"

echo "==> Integration tier PASSED"
