#!/usr/bin/env bash
# Self-test for the merge gate.
#
# The FIRST version of this file passed 14/14 against a gate whose blocking had
# been removed — it asserted the process exit code, but these hooks deny via a
# JSON permissionDecision and exit 0, so exit status carries no information.
# Only 4 of 10 mutations bit. That is the exact fake-green class the retrospective
# this hook came from is about, so every case here now asserts the DECISION
# (parsed out of the JSON) and the mutation list below is part of the contract:
# `bash pre-merge-gate.test.sh --mutations` re-runs them and must report 10/10.
set -u

HOOK="${HOOK:-$(cd "$(dirname "$0")" && pwd)/pre-merge-gate.sh}"
PASS=0; FAIL=0
STUB="$(mktemp -d)"
trap 'rm -rf "$STUB"' EXIT

# --- gh stub: hermetic, no network, no real PRs -----------------------------
cat > "$STUB/gh" <<'STUBEOF'
#!/usr/bin/env bash
args="$*"
case "$args" in
  "pr view --json number"*) printf '%s' "${GH_STUB_CURRENT_PR-}" ;;
  "issue view "*)
    [ "${GH_STUB_ISSUE_FAIL-0}" = "1" ] && exit 1
    printf '%s' "${GH_STUB_ISSUE_BODY-}" ;;
  "pr view "*)
    [ "${GH_STUB_PR_FAIL-0}" = "1" ] && exit 1
    printf '%s' "${GH_STUB_PR_JSON-{\"reviews\":[],\"comments\":[],\"body\":\"\"}}" ;;
esac
STUBEOF
chmod +x "$STUB/gh"
export PATH="$STUB:$PATH"

# Decision, not exit code: these hooks deny with JSON and exit 0.
decide() {
  local out
  out="$(printf '%s' "$1" | bash "$HOOK" 2>/dev/null)"
  case "$out" in
    *'"permissionDecision":"deny"'*) echo deny ;;
    *) echo allow ;;
  esac
}

payload() { printf '{"tool_input":{"command":%s}}' "$(printf '%s' "$1" | jq -Rs .)"; }

run() { # run <name> <expected> <command>
  local name="$1" expect="$2" got
  got="$(decide "$(payload "$3")")"
  if [ "$got" = "$expect" ]; then PASS=$((PASS+1));
  else FAIL=$((FAIL+1)); printf '  ✗ %s — expected %s, got %s\n' "$name" "$expect" "$got"; fi
}

# --- verdict fixtures --------------------------------------------------------
rev()  { printf '{"reviews":[{"submittedAt":"%s","body":"%s"}],"comments":[],"body":"%s"}' "$1" "$2" "${3:-Refs #1}"; }
both() { # review at $1 body $2 ; comment at $3 body $4
  printf '{"reviews":[{"submittedAt":"%s","body":"%s"}],"comments":[{"createdAt":"%s","body":"%s"}],"body":"%s"}' "$1" "$2" "$3" "$4" "${5:-Refs #1}"; }

AC_UNTICKED='## Acceptance criteria
- [x] done
- [ ] not done
- [ ] also not done'
AC_TICKED='## Acceptance criteria
- [x] done
- [x] also done'

echo "== merge gate self-test =="

# 1. Rule 13 — the reason the gate exists.
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "latest verdict REQUEST CHANGES" deny "gh pr merge 284 --squash"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ✅ APPROVED')" \
  run "latest verdict APPROVED" allow "gh pr merge 284 --squash"
GH_STUB_PR_JSON='{"reviews":[],"comments":[],"body":"Refs #1"}' \
  run "no verdict at all" deny "gh pr merge 284 --squash"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z 'Looks good, nice work')" \
  run "verdict without the word APPROVE" deny "gh pr merge 284 --squash"

# 2. NEWEST wins, across BOTH streams — the jq-precedence bug that shipped once.
GH_STUB_PR_JSON="$(both 2026-09-06T10:00:00Z '## ✅ APPROVED' 2026-09-06T11:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "later REQUEST-CHANGES *comment* overrides an approval" deny "gh pr merge 284 --squash"
GH_STUB_PR_JSON="$(both 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES' 2026-09-06T11:00:00Z '## ✅ APPROVED')" \
  run "later APPROVE comment overrides REQUEST CHANGES" allow "gh pr merge 284 --squash"
GH_STUB_PR_JSON='{"reviews":[],"comments":[{"createdAt":"2026-09-06T10:00:00Z","body":"## ✅ APPROVED"}],"body":"Refs #1"}' \
  run "APPROVE posted as a COMMENT (the sanctioned path)" allow "gh pr merge 284 --squash"

# 3. Closes vs unticked acceptance criteria — a blocker four times in v1.12.0.
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ✅ APPROVED' 'Closes #279')" GH_STUB_ISSUE_BODY="$AC_UNTICKED" \
  run "Closes an issue with unticked criteria" deny "gh pr merge 284 --squash"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ✅ APPROVED' 'Refs #279 — AC1 split to #999')" GH_STUB_ISSUE_BODY="$AC_UNTICKED" \
  run "Refs (not Closes) with unticked criteria" allow "gh pr merge 284 --squash"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ✅ APPROVED' 'Closes #279')" GH_STUB_ISSUE_BODY="$AC_TICKED" \
  run "Closes with every criterion ticked" allow "gh pr merge 284 --squash"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ✅ APPROVED' 'Closes #279')" \
GH_STUB_ISSUE_BODY='## Acceptance criteria
- [x] all done

## Follow-ups
- [ ] someday' \
  run "unticked box OUTSIDE the AC section" allow "gh pr merge 284 --squash"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ✅ APPROVED' 'Closes #279')" GH_STUB_ISSUE_FAIL=1 \
  run "issue unreadable -> fail CLOSED" deny "gh pr merge 284 --squash"

# 4. Invocation shapes that used to bypass the gate entirely.
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" GH_STUB_CURRENT_PR=284 \
  run "no PR number (merges current branch)" deny "gh pr merge --squash"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "--repo before the number" deny "gh --repo mavrovde/hirefolio pr merge 284"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "URL form" deny "gh pr merge https://github.com/mavrovde/hirefolio/pull/284"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "env wrapper" deny "env FOO=1 gh pr merge 284"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "leading assignment" deny "FOO=1 gh pr merge 284"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "second segment of a compound command" deny "git status && gh pr merge 284"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "loop-body keyword" deny "for i in 1; do gh pr merge 284; done"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "multi-line command" deny "git status
gh pr merge 284 --squash"

# 5. Quoted prose is DATA (#204/#237) — the false-positive direction.
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "phrase quoted in a comment body" allow "gh pr comment 284 --body 'do not gh pr merge 284 yet'"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "echo of the phrase" allow "echo 'next: gh pr merge 284'"
run "unrelated command" allow "git status"
run "gh pr view is not a merge" allow "gh pr view 284 --json state"
run "git merge is not a PR merge" allow "git merge origin/main"

# The gate blocked its OWN commit before this case existed: a commit message
# quoting `gh pr merge` inside a heredoc read as a command. Heredoc bodies are
# DATA (#212/#237) — this is the false-positive direction, and it is the one
# that stops work rather than merely failing to stop it.
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "commit message heredoc quoting the phrase" allow "git commit -q -F - <<EOF
fix: ten shapes ALLOWED a REQUEST-CHANGES PR, including gh pr merge with no number
EOF"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "quoted heredoc body quoting the phrase" allow "cat > /tmp/body.md <<'MD'
Do not gh pr merge 284 until the review lands.
MD"
# ...but a REAL merge on the line that OPENS a heredoc is still a merge.
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "merge on the heredoc-opening line still gates" deny "gh pr merge 284 --body-file - <<EOF
notes
EOF"

# 6. Fail closed on anything unverifiable.
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ✅ APPROVED')" PR_MERGE_GATE_DEADLINE=0 \
  run "deadline exceeded" deny "gh pr merge 284 --squash"
GH_STUB_PR_FAIL=1 \
  run "PR unreadable" deny "gh pr merge 284 --squash"
GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "no PR number and no current-branch PR" deny "gh pr merge --squash"

# 7. The documented bypass.
PR_MERGE_GATE=0 GH_STUB_PR_JSON="$(rev 2026-09-06T10:00:00Z '## ⛔ REQUEST CHANGES')" \
  run "PR_MERGE_GATE=0" allow "gh pr merge 284 --squash"

echo "merge gate self-test: $PASS passed, $FAIL failed"

# --- Mutation contract -------------------------------------------------------
# `--mutations` proves the cases above actually bite. Each mutation must make at
# least one case fail; 10/10 is the contract. Run in a COPY so the real hook is
# never modified.
if [ "${1-}" = "--mutations" ]; then
  echo
  echo "== mutation contract =="
  MPASS=0; MFAIL=0
  ORIG="$(cat "$HOOK")"
  WORK="$STUB/mutant.sh"
  mutate() { # mutate <name> <sed-expression>
    printf '%s' "$ORIG" | sed -E "$2" > "$WORK"
    chmod +x "$WORK"
    local before_fail=$FAIL
    HOOK="$WORK" bash "$0" >/dev/null 2>&1
    if [ $? -ne 0 ]; then MPASS=$((MPASS+1)); printf '  ✓ killed: %s\n' "$1"
    else MFAIL=$((MFAIL+1)); printf '  ✗ SURVIVED: %s\n' "$1"; fi
  }
  mutate "deny() no longer emits a deny decision"        's/"permissionDecision":\\"deny\\"/"permissionDecision":\\"allow\\"/'
  mutate "REQUEST CHANGES check removed"                 '/latest verdict is REQUEST CHANGES/d'
  mutate "APPROVE requirement removed"                   's/^printf .%s. "\$VERDICT" \| grep -qiE .APPROVE./true/'
  mutate "empty-verdict deny removed"                    '/has no posted review verdict/d'
  mutate "newest-verdict selection reversed"             's/sort_by\(\.at\) \| last/sort_by(.at) | first/'
  mutate "comments stream dropped"                       's/\(\(\.comments \/\/ \[\]\)\[\][^)]*\)//'
  mutate "Closes/AC check removed"                       '/unticked acceptance criteria/d'
  mutate "unreadable issue fails OPEN"                   's/\|\| deny "PR #\$PR_NUM says it closes #\$issue but that issue could not be read[^"]*"/|| continue/'
  mutate "deadline no longer denies"                     '/could not finish within/d'
  mutate "current-branch PR resolution removed"          '/could not determine which PR this merges/d'
  echo "mutation contract: $MPASS killed, $MFAIL survived"
  [ "$MFAIL" -eq 0 ] || exit 1
fi

[ "$FAIL" -eq 0 ]
