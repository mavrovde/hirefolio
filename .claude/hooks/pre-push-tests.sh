#!/usr/bin/env bash
# Pre-push gate for mavrov.de.
#
# Runs a full local check round — docs + backend pytest + backend lint/type
# (ruff + mypy) + frontend unit tests — and BLOCKS a `git push` if anything
# fails. It self-gates by inspecting the
# PreToolUse tool-call JSON on stdin, so it returns "allow" instantly for every
# Bash command that is not a git push (never interferes with normal work).
set -uo pipefail

# ---------------------------------------------------------------------------
# Configurable knobs — override via your shell env or, per-developer, in
# .claude/settings.local.json under "env": { ... } (gitignored, personal).
#   TEST_DATABASE_URL      Postgres URL for the backend pytest run
#   PREPUSH_LOG            where the combined log is written
#   PREPUSH_CHECK_DOCS     1/0 — run the docs check (CHANGELOG [Unreleased] + README)
#   PREPUSH_RUN_GUARDTEST  1/0 — run the destruction-guard hook self-test (#116)
#   PREPUSH_RUN_BACKEND    1/0 — run backend pytest (needs the DB above)
#   PREPUSH_RUN_LINT       1/0 — run backend lint/type leg (ruff + mypy), mirroring CI
#   PREPUSH_RUN_RUFF       1/0 — within the lint leg, run `ruff check .` + `ruff format --check .`
#   PREPUSH_RUN_MYPY       1/0 — within the lint leg, run `mypy app --ignore-missing-imports`
#   PREPUSH_RUN_FRONTEND   1/0 — run frontend shared/public/admin unit tests
# ---------------------------------------------------------------------------
: "${TEST_DATABASE_URL:=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/test_mavrov}"
: "${PREPUSH_LOG:=/tmp/mavrov-prepush-tests.log}"
: "${PREPUSH_CHECK_DOCS:=1}"
: "${PREPUSH_RUN_GUARDTEST:=1}"
: "${PREPUSH_RUN_BACKEND:=1}"
: "${PREPUSH_RUN_LINT:=1}"
: "${PREPUSH_RUN_RUFF:=1}"
: "${PREPUSH_RUN_MYPY:=1}"
: "${PREPUSH_RUN_FRONTEND:=1}"
export TEST_DATABASE_URL

allow() {
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
  exit 0
}
deny() {
  # $1 = reason (plain text, no double quotes)
  printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"$1\"}}"
  exit 0
}

INPUT="$(cat)"
# Extract the command being run (fall back to the raw payload if jq is absent).
CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -z "$CMD" ] && CMD="$INPUT"

# Only gate real pushes; everything else passes through untouched.
case "$CMD" in
  *"git push"*) : ;;
  *) allow ;;
esac

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
LOG="$PREPUSH_LOG"

run_checks() {
  if [ "$PREPUSH_CHECK_DOCS" = "1" ]; then
    echo "== docs check =="
    grep -q "Unreleased" "$ROOT/CHANGELOG.md" || { echo "CHANGELOG.md is missing an [Unreleased] section"; return 1; }
    test -s "$ROOT/README.md" || { echo "README.md is missing or empty"; return 1; }
    echo "== version-consistency check (#172) =="
    ( cd "$ROOT" && ./bump_version.sh --check ) || return 1
    # ...and the checker's own self-test, so an edit to the version tooling fails
    # here rather than first at deploy time (#186).
    ( cd "$ROOT" && bash test-bump-version.sh >/dev/null ) || {
      echo "  ✗ test-bump-version.sh failed — run 'bash test-bump-version.sh' to see which case"
      return 1
    }
  fi

  if [ "$PREPUSH_RUN_GUARDTEST" = "1" ] && [ -f "$ROOT/.claude/hooks/guard-destructive.test.sh" ]; then
    echo "== destruction-guard self-test =="
    bash "$ROOT/.claude/hooks/guard-destructive.test.sh" || return 1
  fi

  if [ "$PREPUSH_RUN_BACKEND" = "1" ]; then
    echo "== backend pytest =="
    # Never run two pytest suites at once: both use the shared test_mavrov DB and
    # do drop_all/create_all per test, clobbering each other into dozens of
    # spurious failures (lessons-learned §4). Fail fast instead of running dirty.
    if pgrep -f pytest >/dev/null 2>&1; then
      echo "Another pytest run is already active (pgrep -f pytest). The shared test_mavrov DB cannot host two suites at once — wait for it to finish, then push again."
      return 1
    fi
    ( cd "$ROOT/backend" && HIREFOLIO_GEMINI_API_KEY="" ./venv/bin/pytest -q ) || return 1
    echo "== agent-playbook drift check (#115) =="
    # Only the sync test: the rest of agents/tests needs the a2a venv. No DB.
    ( cd "$ROOT" && backend/venv/bin/python -m pytest agents/tests/test_playbook_sync.py -q --no-header -p no:cacheprovider --no-cov ) || return 1
  fi

  if [ "$PREPUSH_RUN_LINT" = "1" ]; then
    echo "== backend lint/type (ruff + mypy) =="
    if [ "$PREPUSH_RUN_RUFF" = "1" ]; then
      echo "-- ruff check --"
      ( cd "$ROOT/backend" && ./venv/bin/ruff check . ) || return 1
      echo "-- ruff format --check --"
      ( cd "$ROOT/backend" && ./venv/bin/ruff format --check . ) || return 1
    fi
    if [ "$PREPUSH_RUN_MYPY" = "1" ]; then
      echo "-- mypy --"
      ( cd "$ROOT/backend" && ./venv/bin/mypy app --ignore-missing-imports --no-error-summary ) || return 1
    fi
  fi

  if [ "$PREPUSH_RUN_FRONTEND" = "1" ]; then
    echo "== frontend cd-safety (zoneless repaint hazards, #118) =="
    ( cd "$ROOT/frontend" && node scripts/check-cd-safety.mjs ) || return 1
    echo "== frontend tests (shared + public + admin) =="
    ( cd "$ROOT/frontend" && npm test ) || return 1
  fi
}

if run_checks >"$LOG" 2>&1; then
  allow
else
  deny "Pre-push checks FAILED (docs / backend pytest / backend lint+type ruff+mypy / frontend tests). See $LOG. Configure via env: PREPUSH_RUN_BACKEND, PREPUSH_RUN_LINT, PREPUSH_RUN_RUFF, PREPUSH_RUN_MYPY, PREPUSH_RUN_FRONTEND, PREPUSH_CHECK_DOCS, TEST_DATABASE_URL."
fi
