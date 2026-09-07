#!/usr/bin/env bash
# run_frontend_suites.sh — run the three Vitest projects INDEPENDENTLY, and
# survive one specific upstream flake without ever weakening the gate.
#
# WHY THIS EXISTS (v1.13.0 retrospective, two occurrences):
#   Vitest 4.x can end a fully passing run with an unhandled WORKER-TEARDOWN
#   error — `[vitest-worker]: Closing rpc while "onUserConsoleLog" is pending`
#   (upstream vitest-dev/vitest#8649 / #9872: "Closing rpc while 'fetch' was
#   pending", EnvironmentTeardownError). Measured here: `337/337 tests passed`
#   and a non-zero exit. It hard-failed the whole pre-push gate — once while
#   pushing the v1.13.0 release tag.
#   Worse, `npm test` is `test:shared && test:public && test:admin`, so the
#   teardown flake in `public` meant `admin` NEVER RAN. One upstream race hid
#   two entire suites.
#
# WHAT THIS CHANGES, and what it deliberately does NOT:
#   * every project runs, even if an earlier one failed — you see all three
#     results, and the exit code is still non-zero if ANY project failed;
#   * a project is retried AT MOST ONCE, and only when its output carries the
#     teardown signature AND reports zero failed tests. The retry must pass
#     completely; a second occurrence, a real test failure, or any other error
#     still fails. This is not "retry until green": a genuine failure never
#     matches the signature, and a genuinely flaky TEST does not either.
#   * a survived flake is reported LOUDLY (`⚠ FLAKE`), never silently absorbed.
#   Bumping the runner is #309; do not loosen the gate instead.
#
# Usage: bash scripts/run_frontend_suites.sh [--coverage]
set -u

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
FRONTEND="${FRONTEND_DIR:-$ROOT/frontend}"
NPM="${NPM_BIN:-npm}"
PROJECTS="${FRONTEND_PROJECTS:-shared public admin}"
SUFFIX=""
[ "${1-}" = "--coverage" ] && SUFFIX="coverage:"

# The ONE tolerated signature. Keep it narrow and keep the issue numbers with it.
TEARDOWN_RE='Closing rpc while|EnvironmentTeardownError'

overall=0
flakes=0
for p in $PROJECTS; do
  target="test:${SUFFIX}${p}"
  out="$( (cd "$FRONTEND" && "$NPM" run "$target" 2>&1) )"; rc=$?
  printf '%s\n' "$out"
  if [ "$rc" -eq 0 ]; then
    printf '  ✓ %s\n' "$target"
    continue
  fi
  # Retry ONLY the upstream teardown race, and only with no failed tests.
  if printf '%s' "$out" | grep -qE "$TEARDOWN_RE" \
     && ! printf '%s' "$out" | grep -qE '[1-9][0-9]* failed'; then
    printf '  ⚠ FLAKE: %s exited %d with the Vitest worker-teardown race and ZERO failed tests — retrying ONCE (env-gotchas, #309)\n' \
      "$target" "$rc"
    out="$( (cd "$FRONTEND" && "$NPM" run "$target" 2>&1) )"; rc=$?
    printf '%s\n' "$out"
    if [ "$rc" -eq 0 ]; then
      printf '  ⚠ FLAKE SURVIVED: %s passed on the retry. Not a code failure — record it, do not ignore it.\n' "$target"
      flakes=$((flakes+1))
      continue
    fi
    printf '  ✗ %s failed AGAIN on the retry — this is not the tolerated flake.\n' "$target"
  fi
  printf '  ✗ %s FAILED (exit %d)\n' "$target" "$rc"
  overall=1
done

[ "$flakes" -gt 0 ] && printf '\n⚠ %d project(s) needed the teardown retry this run.\n' "$flakes"
[ "$overall" -eq 0 ] && printf '\n✓ all frontend projects passed: %s\n' "$PROJECTS"
exit "$overall"
