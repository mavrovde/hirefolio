#!/usr/bin/env bash
# Merge gate (v1.12.0 retrospective): rule 13 and the Closes/AC contract,
# enforced mechanically instead of asked for in prose.
#
# WHY THIS EXISTS — measured over v1.12.0's review verdicts:
#   * Rule 13 (independent APPROVE before merge) is restated across eleven
#     files with zero mechanical enforcement anywhere.
#   * `Closes #NN` against an issue with unticked acceptance criteria was a
#     BLOCKER in four PRs (#254, #257, #258, #284). Every one was caught only
#     because a review read the issue by hand. A `Closes` decides the issue's
#     fate automatically at merge, so an unmet criterion closes silently.
#
# Merging is the sanctioned prod-deploy trigger (rule 8) — the irreversible
# moment this repo already guards elsewhere. Therefore this hook FAILS CLOSED:
# anything it cannot analyse or verify is a deny, never an allow.
#
# Bypass ONE authorized merge with:  PR_MERGE_GATE=0 gh pr merge <N> ...
set -u

DEADLINE_SECONDS="${PR_MERGE_GATE_DEADLINE:-25}"
START=$SECONDS

allow() { exit 0; }
deny() {
  # Same JSON contract as the sibling hooks: a structured deny, exit 0.
  printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"MERGE GATE: $1 | Bypass one authorized command with PR_MERGE_GATE=0\"}}"
  exit 0
}

[ "${PR_MERGE_GATE:-1}" = "0" ] && allow

# Extract the command with jq, like both siblings. A hand-rolled sed
# over-captured on multi-line payloads and was the root of several bypasses.
INPUT="$(cat)"
CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"
if [ -z "$CMD" ]; then
  # Degraded path: the command text is invisible, so merge-absence cannot be
  # proven. A merge-looking payload GATES (the sibling hooks' polarity).
  case "$INPUT" in
    *"pr merge"*) CMD="gh pr merge" ;;
    *) allow ;;
  esac
fi

# FAST PATH — this hook self-gates on EVERY Bash call, so a command with no
# merge-like text must return instantly, before sourcing anything.
case "$CMD" in
  *merge*) : ;;
  *) allow ;;
esac

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hook-parse-lib.sh"
INSPECT_DEADLINE=$((START + DEADLINE_SECONDS))

# Does this SEGMENT (separator-split, quote-aware) invoke `gh pr merge`?
# Reuses the SHARED peel model, so wrappers (`env X=1 gh …`, `sudo`, `timeout`),
# compound-command keywords (`do gh pr merge …` in a loop body), alias-suppressed
# spellings and leading assignments are handled exactly as the pre-push gate
# handles `git push` — and `gh pr merge` inside a quoted argument stays DATA
# (#204/#237).
segment_invokes_pr_merge() {
  local seg="$1"
  [ "$SECONDS" -ge "$INSPECT_DEADLINE" ] && return 0   # cannot analyse → gate
  seg="$(printf '%s' "$seg" | tr '\n\t' '  ' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+/ /g')"

  local changed=1 loops=0
  while [ "$changed" = "1" ] && [ "$loops" -lt 8 ]; do
    changed=0; loops=$((loops + 1))
    [ "$SECONDS" -ge "$INSPECT_DEADLINE" ] && return 0
    [ "${seg:0:1}" = '\' ] && { seg="${seg#\\}"; changed=1; }
    case "$seg" in
      "do "*|"then "*|"else "*|"elif "*|"{ "*|"( "*) seg="${seg#* }"; changed=1 ;;
    esac
    while [[ "$seg" =~ ^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+ ]]; do
      seg="${seg#* }"; changed=1
    done
    if command -v peel_wrapper >/dev/null 2>&1; then
      PEEL_RESULT=""
      if peel_wrapper "$seg" && [ -n "${PEEL_RESULT:-}" ] && [ "$PEEL_RESULT" != "$seg" ]; then
        seg="$PEEL_RESULT"; changed=1
      fi
    fi
  done

  # Command word must be `gh`, then the subcommand pair `pr merge` — with gh's
  # value-taking globals consumed in between, so `gh --repo x pr merge 1` is
  # caught exactly like `gh pr merge 1 --repo x`.
  # IFS is $'\n' in the caller's loop, so a bare `set -- $seg` would NOT split
  # on spaces and the whole segment would arrive as one positional parameter —
  # every wrapper and compound case then reads as "not a merge" and the gate
  # allows. Restore word splitting locally.
  local IFS=' '
  # shellcheck disable=SC2086
  set -- $seg
  [ "${1:-}" = "gh" ] || return 1
  shift
  while [ $# -gt 0 ]; do
    case "$1" in
      --repo|-R|--hostname) shift; shift || return 1 ;;
      --repo=*|-R=*|--hostname=*|-*) shift ;;
      *) break ;;
    esac
  done
  [ "${1:-}" = "pr" ] || return 1
  shift
  [ "${1:-}" = "merge" ] || return 1
  return 0
}

MERGE_SEG=""
OLD_IFS="$IFS"
IN_HEREDOC_DELIM=""
while IFS= read -r line; do
  # HEREDOC BODIES ARE DATA, NOT COMMANDS. A commit message, a PR body or a
  # review quoted through `git commit -F -`/`gh pr create --body-file` routinely
  # contains the literal text `gh pr merge` — and this gate blocked its own
  # commit that way before this branch existed. The shared lib already models
  # heredocs for exactly this reason (#212/#237); skip a body until its
  # delimiter. (A heredoc whose body is then EXECUTED — `bash <<EOF` — is the
  # dangerous shape the sibling guard analyses; a merge inside one is not
  # reachable here without also passing the `gh` command-word check on the outer
  # line, so treating bodies as data is safe for THIS gate.)
  if [ -n "$IN_HEREDOC_DELIM" ]; then
    trimmed="${line#"${line%%[![:space:]]*}"}"
    [ "$trimmed" = "$IN_HEREDOC_DELIM" ] && IN_HEREDOC_DELIM=""
    continue
  fi
  delim="$(heredoc_delim "$line" 2>/dev/null || true)"
  if [ -n "$delim" ]; then
    IN_HEREDOC_DELIM="$delim"
    # The line introducing the heredoc is still a real command line; inspect it.
  fi
  IFS=$'\n'
  for seg in $(quote_split "$line"); do
    if segment_invokes_pr_merge "$seg"; then MERGE_SEG="$seg"; fi
  done
  IFS="$OLD_IFS"
done <<< "$CMD"
IFS="$OLD_IFS"

[ -z "$MERGE_SEG" ] && allow

command -v gh >/dev/null 2>&1 || deny "gh is not on PATH, so the review verdict cannot be checked"
command -v jq >/dev/null 2>&1 || deny "jq is not on PATH, so the review verdict cannot be checked"

past_deadline() { [ $((SECONDS - START)) -ge "$DEADLINE_SECONDS" ]; }
past_deadline && deny "could not finish within ${DEADLINE_SECONDS}s — an unanalysed merge must not proceed"

# Which PR? `gh pr merge` with no argument merges the CURRENT BRANCH's PR — the
# most natural invocation, and previously an unconditional bypass. A URL form
# (`gh pr merge https://…/pull/291`) is normalised first.
PR_NUM="$(printf '%s' "$MERGE_SEG" \
  | sed -E 's#https?://[^ ]*/pull/([0-9]+)#\1#g' \
  | sed -n 's/.*merge[[:space:]]\{1,\}\([0-9]\{1,\}\).*/\1/p' | head -1)"
if [ -z "$PR_NUM" ]; then
  PR_NUM="$(gh pr view --json number --jq '.number' 2>/dev/null)"
  [ -z "$PR_NUM" ] && deny "could not determine which PR this merges (no number given, and no PR found for the current branch) — refusing to merge unverified"
fi

# --- Check 1: rule 13 — the LATEST verdict must be an approval --------------
# `gh pr review --approve` is blocked for a same-identity author, so the repo's
# sanctioned path is a COMMENT verdict whose body states APPROVE. Both streams
# count and the NEWEST wins, so a later REQUEST CHANGES overrides an approval.
PR_JSON="$(gh pr view "$PR_NUM" --json reviews,comments,body 2>/dev/null)" \
  || deny "could not read PR #$PR_NUM (network or auth) — refusing to merge unverified"
past_deadline && deny "could not finish within ${DEADLINE_SECONDS}s — an unanalysed merge must not proceed"

# NOTE the parenthesised streams. `|` binds looser than `,`, so without them the
# expression silently becomes `.reviews[] | (…, .comments[]) | …`: `at` is always
# null (sort_by a no-op, "newest wins" unimplemented) and comments are never
# read. That bug shipped once and made the gate deny the repo's own sanctioned
# APPROVE path while allowing a later REQUEST CHANGES.
VERDICT="$(printf '%s' "$PR_JSON" | jq -r '
  [ ((.reviews // [])[]  | {at: .submittedAt, body: (.body // "")}),
    ((.comments // [])[] | {at: .createdAt,   body: (.body // "")}) ]
  | map(select(.at != null and (.body | test("APPROVE|APPROVED|REQUEST CHANGES"; "i"))))
  | sort_by(.at) | last | .body // ""' 2>/dev/null)"

[ -z "$VERDICT" ] && deny "PR #$PR_NUM has no posted review verdict — rule 13 requires an independent pr-reviewer APPROVE before merge"

if printf '%s' "$VERDICT" | grep -qiE 'REQUEST CHANGES'; then
  deny "PR #$PR_NUM's latest verdict is REQUEST CHANGES — fix the findings in this PR first (rule 11)"
fi
printf '%s' "$VERDICT" | grep -qiE 'APPROVE' \
  || deny "PR #$PR_NUM's latest verdict does not state APPROVE (rule 13)"

# --- Check 2: `Closes #NN` must not point at unticked criteria ---------------
BODY="$(printf '%s' "$PR_JSON" | jq -r '.body // ""')"
CLOSES="$(printf '%s' "$BODY" | grep -oiE '(closes|fixes|resolves)[[:space:]]+#[0-9]+' | grep -oE '[0-9]+' | sort -u)"

for issue in $CLOSES; do
  past_deadline && deny "could not finish within ${DEADLINE_SECONDS}s — an unanalysed merge must not proceed"
  # FAIL CLOSED: an unreadable issue is not evidence that its criteria are met.
  IBODY="$(gh issue view "$issue" --json body --jq '.body // ""' 2>/dev/null)" \
    || deny "PR #$PR_NUM says it closes #$issue but that issue could not be read — refusing to close an issue whose criteria are unverified"
  # Heading match tolerates bold and all-caps; BWK-awk portable (no IGNORECASE).
  UNCHECKED="$(printf '%s' "$IBODY" \
    | awk '/^#+.*([Aa]cceptance|ACCEPTANCE).*([Cc]riteria|CRITERIA)/{f=1;next} f&&/^#+ /{f=0} f' \
    | grep -cE '^[[:space:]]*[-*][[:space:]]*\[[[:space:]]\]' || true)"
  if [ "${UNCHECKED:-0}" -gt 0 ]; then
    deny "PR #$PR_NUM says it closes #$issue, but #$issue has $UNCHECKED unticked acceptance criteria — use 'Refs #$issue' and name the unmet criterion, or tick them with what you ran"
  fi
done

exit 0
