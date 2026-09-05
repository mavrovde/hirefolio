#!/usr/bin/env bash
# ONE freshness contract, two callers (#169): the scheduled Live Freshness
# workflow and deploy.yml's post-rollout gate both source their verdict here,
# so the probes cannot drift apart (the bump_version.sh --check pattern).
#
#   check_live_freshness.sh <PUBLIC_URL> <RELEASED_VERSION>
#
# Exit codes:  0 fresh · 1 stale · 2 unreachable (distinct on purpose — a down
# site is an outage, not a pre-split frontend; #254 review finding).
# Output: one "key value verdict" line per probe, parseable and summary-ready.
set -u

PUBLIC_URL="${1:?usage: check_live_freshness.sh <PUBLIC_URL> <RELEASED_VERSION>}"
RELEASED="${2:?usage: check_live_freshness.sh <PUBLIC_URL> <RELEASED_VERSION>}"
PUBLIC_URL="${PUBLIC_URL%/}"

fail=0

stats=$(curl -s -m 15 "$PUBLIC_URL/api/app/stats/public" || echo '')
live=$(printf '%s' "$stats" | jq -r '.backend_version // empty' 2>/dev/null || echo '')

if [ -z "$live" ]; then
  echo "backend_version unreachable DOWN"
  fail=2
elif [ "$live" != "$RELEASED" ]; then
  echo "backend_version $live STALE(want=$RELEASED)"
  fail=1
else
  echo "backend_version $live fresh"
fi

# Post-workspace-split shape probe: the public host must NOT serve the admin
# SPA route. -L so a future legitimate redirect is judged by its FINAL status.
code=$(curl -s -L -o /dev/null -w '%{http_code}' -m 15 "$PUBLIC_URL/admin/login")
case "$code" in
  404) echo "admin_route 404 fresh" ;;
  000)
    echo "admin_route unreachable DOWN"
    [ "$fail" -eq 0 ] && fail=2 ;;
  *)
    echo "admin_route $code STALE(want=404,pre-split-frontend)"
    [ "$fail" -eq 0 ] && fail=1 ;;
esac

exit "$fail"
