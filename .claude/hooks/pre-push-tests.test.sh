#!/usr/bin/env bash
# Self-test for pre-push-tests.sh's SELF-GATE (issue #237).
# Run: bash pre-push-tests.test.sh — exits non-zero if any case regresses.
#
# Each case feeds a PreToolUse-shaped JSON on stdin with PREPUSH_DRY_RUN=1, so
# the hook prints its self-gate decision — GATE (a real push: run the check
# round) or ALLOW (not a push: pass through instantly) — WITHOUT running any
# suite. Both directions of #237 are pinned:
#   - a real push GATES, including inside loops / compounds / wrappers /
#     shell -c bodies (the observed false-negative);
#   - quoted PROSE mentioning a push ALLOWS — PR-review bodies, commit
#     messages, heredoc documents (the #204 false-positive class).
#
# The push phrase is assembled from parts (P below, §21.8 of lessons-learned)
# so this file's own text never contains it contiguously — the OLD substring
# matcher would otherwise gate on any tool-call that touches this file.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/pre-push-tests.sh"
fails=0

P="git pu""sh"          # "git <push>" — assembled so it never appears verbatim
PU="pu""sh"             # the bare subcommand

check() { # desc cmd expect(GATE|ALLOW)
  local desc="$1" cmd="$2" expect="$3" out
  out="$(printf '{"tool_input":{"command":%s}}' "$(jq -Rn --arg c "$cmd" '$c')" \
        | PREPUSH_DRY_RUN=1 bash "$HOOK")"
  if [ "$out" = "$expect" ]; then
    printf 'PASS  [%s]  %s\n' "$out" "$desc"
  else
    printf 'FAIL  got=%s want=%s  %s\n' "$out" "$expect" "$desc"
    fails=$((fails + 1))
  fi
}

# Wall-clock assertion: the hook self-gates on EVERY Bash call, so the
# non-candidate path must stay near-instant (no parsing, no forks) and even
# candidates must decide well inside the harness timeout.
check_fast() { # desc cmd max_seconds
  local desc="$1" cmd="$2" max="$3" t0 t1 el
  t0=$(date +%s)
  printf '{"tool_input":{"command":%s}}' "$(jq -Rn --arg c "$cmd" '$c')" \
    | PREPUSH_DRY_RUN=1 bash "$HOOK" >/dev/null
  t1=$(date +%s); el=$((t1 - t0))
  if [ "$el" -le "$max" ]; then
    printf 'PASS  [%ss<=%ss]  %s\n' "$el" "$max" "$desc"
  else
    printf 'FAIL  took=%ss max=%ss  %s\n' "$el" "$max" "$desc"
    fails=$((fails + 1))
  fi
}

# --- direction 1: a REAL push must GATE -------------------------------------
check "bare push"                    "$P origin main"                          GATE
check "push, no args"                "$P"                                      GATE
check "push with flags"              "$P --force-with-lease origin HEAD"       GATE
check "git -C dir push"              "git -C /some/worktree $PU origin main"   GATE
check "git -c val push"              "git -c push.default=current $PU"         GATE
check "push after cd &&"             "cd frontend && $P origin HEAD"           GATE
check "push at end of && chain"      "git add -A && git commit -m \"x\" && $P" GATE
check "push after semicolon"         "git commit -m \"done\"; $P origin HEAD"  GATE
check "push in for-loop body"        "for b in a b; do $P origin \$b; done"    GATE
check "push in while-loop body"      "while true; do $P; done"                 GATE
check "backgrounded compound loop"   "(for b in x; do $P origin \$b; done) &"  GATE
check "push in if-condition"         "if $P; then echo ok; fi"                 GATE
check "sudo push"                    "sudo $P origin main"                     GATE
check "env wrapper push"             "env GIT_TRACE=1 $P"                      GATE
check "timeout wrapper push"         "timeout 600 $P origin main"              GATE
check "env-assignment prefix push"   "GIT_SSH_COMMAND=ssh $P origin main"      GATE
check "alias-suppressed push"        "\\$P origin main"                        GATE
check "bash -c push"                 "bash -c \"$P origin main\""              GATE
check "sh -lc push"                  "sh -lc '$P origin main'"                 GATE
check "eval push"                    "eval \"$P origin main\""                 GATE
check "ssh remote push"              "ssh host \"cd /srv/repo && $P\""         GATE
check "xargs push"                   "echo origin | xargs $P"                  GATE
check "heredoc fed to bash"          "bash <<'EOF'
$P origin main
EOF"                                                                           GATE
check "push on 2nd line of script"   "git add -A
$P origin main"                                                                GATE

# --- direction 2: PROSE mentioning a push must ALLOW ------------------------
check "pr comment quoting push"      "gh pr comment 1 --body \"run $P origin main afterwards\""  ALLOW
check "review body, multiline quote" "gh pr review 211 --approve --body \"looks good
$P origin main
ship it\""                                                                     ALLOW
check "quoted line STARTS with push" "gh pr comment 1 --body \"$P origin main is the deploy trigger\"" ALLOW
check "issue comment quoting push"   "gh issue comment 9 --body \"the fix: $P --force-with-lease\""    ALLOW
check "heredoc prose quoting push"   "cat > /tmp/review.md <<'EOF'
Then run: $P origin main
EOF"                                                                           ALLOW
check "heredoc line IS the phrase"   "cat > notes.md <<'EOF'
$P origin main
EOF"                                                                           ALLOW
check "heredoc body-file combo"      "cat > /tmp/b.md <<'EOF'
quoting $P here for the record
EOF
gh pr comment 5 --body-file /tmp/b.md"                                         ALLOW
check "echo quoted push"             "echo \"$P\""                             ALLOW
check "echo unquoted push words"     "echo $P origin main"                     ALLOW
check "printf quoting push"          "printf '%s' 'about $P origin'"           ALLOW
check "commit msg mentions push"     "git commit -m \"then $P\""               ALLOW
check "commit msg IS the phrase"     "git commit -m \"$P origin main\""        ALLOW
check "commit prose then status"     "git commit -m \"docs: how to $P\" && git status" ALLOW
check "grep for the phrase"          "grep -rn \"$P\" docs/"                   ALLOW
check "git log --grep push"          "git log --grep=\"$P --force\""           ALLOW
check "push substring, no push cmd"  "npm run build && echo pushed to registry" ALLOW
check "git pull is not push"         "git pull origin main"                    ALLOW
check "plain command, no push text"  "ls -la"                                  ALLOW
check "body-file, no push text"      "gh pr review 211 --body-file /tmp/review.md" ALLOW

# --- both directions at once ------------------------------------------------
check "prose AND a real push"        "git commit -m \"then $P\" && $P origin HEAD" GATE

# --- degraded path: unparseable payload (no .tool_input.command) ------------
# Without a command field the real text is invisible; push-looking payloads
# keep the old conservative substring behaviour (GATE), others pass.
raw_check() { # desc raw_stdin expect
  local desc="$1" raw="$2" expect="$3" out
  out="$(printf '%s' "$raw" | PREPUSH_DRY_RUN=1 bash "$HOOK")"
  if [ "$out" = "$expect" ]; then
    printf 'PASS  [%s]  %s\n' "$out" "$desc"
  else
    printf 'FAIL  got=%s want=%s  %s\n' "$out" "$expect" "$desc"
    fails=$((fails + 1))
  fi
}
raw_check "degraded: raw push text"  "not json but $P is in here"              GATE
raw_check "degraded: raw, no push"   "not json, nothing push-shaped beyond the word pushkin" ALLOW

# --- bounds: too big to analyse must GATE, never fast-allow -----------------
big="gh pr comment 1 --body \"$(printf 'prose %.0s' $(seq 1 40)) $P quoted\""
out="$(printf '{"tool_input":{"command":%s}}' "$(jq -Rn --arg c "$big" '$c')" \
      | PREPUSH_DRY_RUN=1 PREPUSH_MAX_CMD_LEN=50 bash "$HOOK")"
if [ "$out" = "GATE" ]; then
  printf 'PASS  [GATE]  size bound exceeded gates (conservative polarity)\n'
else
  printf 'FAIL  got=%s want=GATE  size bound exceeded gates\n' "$out"
  fails=$((fails + 1))
fi

# --- hook-JSON contract (no dry run) ----------------------------------------
# Not-a-push emits the allow decision JSON…
out="$(printf '{"tool_input":{"command":"ls -la"}}' | bash "$HOOK")"
dec="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision')"
if [ "$dec" = "allow" ]; then
  printf 'PASS  [allow]  JSON contract: non-push fast path\n'
else
  printf 'FAIL  got=%s want=allow  JSON contract: non-push fast path\n     -> %s\n' "$dec" "$out"
  fails=$((fails + 1))
fi
# …and a REAL push reaches the check round: with every leg switched off the
# round trivially passes and the allow JSON is emitted end-to-end.
out="$(printf '{"tool_input":{"command":%s}}' "$(jq -Rn --arg c "$P origin main" '$c')" \
      | PREPUSH_CHECK_DOCS=0 PREPUSH_RUN_GUARDTEST=0 PREPUSH_RUN_BACKEND=0 \
        PREPUSH_RUN_LINT=0 PREPUSH_RUN_FRONTEND=0 PREPUSH_LOG=/tmp/prepush-selftest.log \
        bash "$HOOK")"
dec="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision')"
if [ "$dec" = "allow" ]; then
  printf 'PASS  [allow]  JSON contract: gated push runs the (emptied) round\n'
else
  printf 'FAIL  got=%s want=allow  JSON contract: gated push runs the round\n     -> %s\n' "$dec" "$out"
  fails=$((fails + 1))
fi

# --- cost: the self-gate runs on EVERY Bash call ----------------------------
check_fast "cost: non-candidate is instant"  "npm run test:coverage"           2
bulk="$(printf 'echo prose line %.0s' $(seq 1 300))"
check_fast "cost: 5KB non-candidate"         "$bulk"                          2
check_fast "cost: 4KB prose candidate"       "gh pr comment 1 --body \"$(printf 'words %.0s' $(seq 1 500)) $P quoted\"" 8

echo
if [ "$fails" -gt 0 ]; then
  echo "$fails pre-push self-gate case(s) FAILED."
  exit 1
fi
echo "All pre-push self-gate cases passed."
