#!/usr/bin/env bash
# Performance smoke via JMeter-in-Docker (#260) — no local Java needed.
#
#   ./backend/perf/run_jmeter.sh                       # defaults: 10 threads, 60 s
#   THREADS=25 DURATION=120 ./backend/perf/run_jmeter.sh
#   BUDGET_READ_MS=1 ./backend/perf/run_jmeter.sh      # negative test: must FAIL
#
# The target stack must already be running (./manage.sh start or the
# integration stack). Results: backend/perf/results/<timestamp>/ with the
# JMeter HTML dashboard. Exit is NON-ZERO when any assertion (status or
# duration budget) failed — budgets are executable, not decorative.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HERE/results/$STAMP"
mkdir -p "$OUT"

HOST="${HOST:-host.docker.internal}"
PORT="${PORT:-8000}"
THREADS="${THREADS:-10}"
DURATION="${DURATION:-60}"
BUDGET_READ_MS="${BUDGET_READ_MS:-800}"
IMAGE="${JMETER_IMAGE:-alpine/jmeter:5.6.3}"

echo "==> JMeter smoke: ${THREADS} threads, ${DURATION}s, budget ${BUDGET_READ_MS}ms -> $OUT"
docker run --rm \
  --add-host host.docker.internal:host-gateway \
  -v "$HERE":/plan:ro \
  -v "$OUT":/out \
  "$IMAGE" \
  -n -t /plan/smoke.jmx \
  -Jhost="$HOST" -Jport="$PORT" \
  -Jthreads="$THREADS" -Jduration="$DURATION" \
  -Jbudget_read_ms="$BUDGET_READ_MS" \
  -l /out/results.jtl -e -o /out/dashboard

# JTL rows are RFC-4180 CSV: responseMessage may contain quoted commas, so any
# field-splitting on bare "," miscounts and fails OPEN (#261 review, round 2 —
# the header-index awk variant had the same hole because only DATA rows shift).
# Parse it as CSV for real; python3 is present on CI runners and dev machines.
counts=$(python3 - "$OUT/results.jtl" <<'PYCSV'
import csv, sys
with open(sys.argv[1], newline="") as fh:
    rows = list(csv.DictReader(fh))
print(len(rows), sum(1 for r in rows if r.get("success") == "false"))
PYCSV
)
total=${counts% *}
failed=${counts#* }

echo "==> Samples: $total, failed: $failed"
echo "==> Dashboard: $OUT/dashboard/index.html"

if [ "$total" -eq 0 ]; then
  echo "FATAL: no samples recorded — is the stack up at $HOST:$PORT?"
  exit 2
fi
if [ "$failed" -gt 0 ]; then
  echo "FAIL: $failed sample(s) violated a status or duration-budget assertion."
  exit 1
fi
echo "PASS: all samples within budget."
