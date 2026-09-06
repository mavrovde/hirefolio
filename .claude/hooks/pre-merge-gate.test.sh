#!/usr/bin/env bash
# Self-test for the merge gate. Every hook in this repo carries one, because a
# guard whose behavior nobody pins is a guard nobody can trust (lessons §16/§18).
#
# `gh` is stubbed on PATH so the cases are hermetic: no network, no real PRs.
set -u

HOOK="$(cd "$(dirname "$0")" && pwd)/pre-merge-gate.sh"
PASS=0; FAIL=0
STUB="$(mktemp -d)"
trap 'rm -rf "$STUB"' EXIT

# --- gh stub -----------------------------------------------------------------
# Behavior is driven by env so each case can shape the fixture it needs.
cat > "$STUB/gh" <<'STUBEOF'
#!/usr/bin/env bash
case "$1 $2 $3" in
  "pr view "*)
    cat <<JSON
{"reviews":[{"submittedAt":"2026-09-06T10:00:00Z","body":"${GH_STUB_VERDICT-## ✅ APPROVED}"}],
 "comments":[],
 "body":"${GH_STUB_PR_BODY-Refs #1}"}
JSON
    ;;
  "issue view "*)
    printf '%s' "${GH_STUB_ISSUE_BODY-}"
    ;;
esac
STUBEOF
chmod +x "$STUB/gh"
export PATH="$STUB:$PATH"

run() { # run <name> <expected: allow|deny> <command-string>
  local name="$1" expect="$2" cmd="$3" out rc
  out="$(printf '{"tool_input":{"command":"%s"}}' "$cmd" | bash "$HOOK" 2>&1)"; rc=$?
  local got="allow"; [ $rc -ne 0 ] && got="deny"
  if [ "$got" = "$expect" ]; then
    PASS=$((PASS+1))
  else
    FAIL=$((FAIL+1))
    printf '  ✗ %s — expected %s, got %s\n    %s\n' "$name" "$expect" "$got" "$(printf '%s' "$out" | head -2)"
  fi
}

echo "== merge gate self-test =="

# 1. Rule 13 — the reason the gate exists.
GH_STUB_VERDICT='## ⛔ REQUEST CHANGES (round 2)' \
  run "latest verdict REQUEST CHANGES -> deny" deny "gh pr merge 284 --squash"
GH_STUB_VERDICT='## ✅ APPROVED — round 3' \
  run "latest verdict APPROVED -> allow" allow "gh pr merge 284 --squash"
GH_STUB_VERDICT='' \
  run "no verdict at all -> deny" deny "gh pr merge 284 --squash"
GH_STUB_VERDICT='Looks fine to me, nice work' \
  run "verdict without the word APPROVE -> deny" deny "gh pr merge 284 --squash"

# 2. Closes vs unticked acceptance criteria — a blocker four times in v1.12.0.
GH_STUB_VERDICT='## ✅ APPROVED' \
GH_STUB_PR_BODY='Closes #279' \
GH_STUB_ISSUE_BODY='## Acceptance criteria
- [x] backend done
- [ ] Button disabled during flight (spec pins it)
- [ ] documented' \
  run "Closes an issue with unticked criteria -> deny" deny "gh pr merge 284 --squash"

GH_STUB_VERDICT='## ✅ APPROVED' \
GH_STUB_PR_BODY='Refs #279 — AC1 is out of scope, split to #999' \
GH_STUB_ISSUE_BODY='## Acceptance criteria
- [x] backend done
- [ ] Button disabled during flight' \
  run "Refs (not Closes) with unticked criteria -> allow" allow "gh pr merge 284 --squash"

GH_STUB_VERDICT='## ✅ APPROVED' \
GH_STUB_PR_BODY='Closes #279' \
GH_STUB_ISSUE_BODY='## Acceptance criteria
- [x] backend done
- [x] Button disabled during flight' \
  run "Closes with every criterion ticked -> allow" allow "gh pr merge 284 --squash"

# A checklist OUTSIDE the acceptance-criteria section must not block (a PR-style
# task list in the issue body is not the contract a Closes decides).
GH_STUB_VERDICT='## ✅ APPROVED' \
GH_STUB_PR_BODY='Closes #279' \
GH_STUB_ISSUE_BODY='## Acceptance criteria
- [x] all done

## Follow-ups
- [ ] someday maybe' \
  run "unticked box outside the AC section -> allow" allow "gh pr merge 284 --squash"

# 3. Quoted prose is DATA, not a command (#204/#237) — the regression class that
#    the shared parsing model exists for.
GH_STUB_VERDICT='## ⛔ REQUEST CHANGES' \
  run "quoted mention in a comment -> allow" allow "gh pr comment 284 --body \\\"do not gh pr merge 284 yet\\\""
GH_STUB_VERDICT='## ⛔ REQUEST CHANGES' \
  run "echo of the phrase -> allow" allow "echo \\\"next step: gh pr merge 284\\\""

# 4. Unrelated commands are untouched.
run "unrelated command -> allow" allow "git status"
run "gh pr view is not a merge -> allow" allow "gh pr view 284 --json state"

# 5. The documented bypass.
PR_MERGE_GATE=0 GH_STUB_VERDICT='## ⛔ REQUEST CHANGES' \
  run "PR_MERGE_GATE=0 bypass -> allow" allow "gh pr merge 284 --squash"

# 6. Fail CLOSED when the verdict cannot be established (merge is the prod trigger).
GH_STUB_VERDICT='## ✅ APPROVED' PR_MERGE_GATE_DEADLINE=0 \
  run "deadline exceeded -> deny" deny "gh pr merge 284 --squash"

echo "merge gate self-test: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
