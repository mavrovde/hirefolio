#!/usr/bin/env bash
# Merge gate (v1.12.0 retrospective): rule 13 and the Closes/AC contract, enforced
# mechanically instead of asked for in prose.
#
# WHY THIS EXISTS — measured over v1.12.0's 34 review verdicts:
#   * Rule 13 (independent APPROVE before merge) is restated in SIX places —
#     CLAUDE.md, backend-dev, frontend-dev, pr-reviewer, release-manager,
#     env-gotchas — with zero mechanical enforcement anywhere.
#   * `Closes #NN` against an issue with unticked acceptance criteria was a
#     BLOCKER in four PRs (#254, #257, #258, #284). Every one was caught by a
#     very expensive human-equivalent review reading the issue by hand. A
#     `Closes` decides the issue's fate automatically at merge, so an unmet
#     criterion is closed silently.
#
# Merging is the sanctioned prod-deploy trigger (rule 8), i.e. exactly the
# irreversible moment this repo already guards elsewhere.
#
# Bypass ONE authorized merge with:  PR_MERGE_GATE=0 gh pr merge <N> ...
set -u

# Quoted prose is data, not a command (#204/#237) — share the ONE parsing model.
LIB="$(dirname "$0")/hook-parse-lib.sh"
[ -f "$LIB" ] && . "$LIB"

DEADLINE_SECONDS="${PR_MERGE_GATE_DEADLINE:-25}"
START=$SECONDS

allow() { exit 0; }
deny() {
  printf 'BLOCKED by the merge gate: %s\n' "$1" >&2
  printf 'Fix it, or bypass this ONE command with: PR_MERGE_GATE=0 <command>\n' >&2
  exit 2
}

[ "${PR_MERGE_GATE:-1}" = "0" ] && allow

# ---------------------------------------------------------------------------
# Read the tool input; find a REAL `gh pr merge <N>` in command position.
# ---------------------------------------------------------------------------
INPUT="$(cat 2>/dev/null || true)"
CMD="$(printf '%s' "$INPUT" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' | head -1)"
[ -z "$CMD" ] && allow

# Cheap pre-filter: nothing that mentions the phrase at all can be a merge.
case "$CMD" in
  *"gh pr merge"*) ;;
  *) allow ;;
esac

# Command-position check: `echo "run gh pr merge 12"` must NOT trigger the gate.
# When the shared lib is unavailable, fail CLOSED (see the deadline rationale).
IN_COMMAND_POSITION=0
MERGE_SEG=""
if command -v quote_split >/dev/null 2>&1; then
  OLD_IFS="$IFS"
  while IFS= read -r line; do
    IFS=$'\n'
    for seg in $(quote_split "$line"); do
      seg="${seg#"${seg%%[![:space:]]*}"}"
      case "$seg" in
        "gh pr merge "*|"gh pr merge") IN_COMMAND_POSITION=1; MERGE_SEG="$seg" ;;
      esac
    done
    IFS="$OLD_IFS"
  done <<< "$CMD"
  IFS="$OLD_IFS"
  # Quoted prose mentioning the phrase is DATA, not a merge (#204/#237).
  [ "$IN_COMMAND_POSITION" = "1" ] || allow
else
  # The shared parser is the ONE model; without it we cannot tell a command from
  # quoted prose, so fail closed on anything that mentions the phrase.
  MERGE_SEG="$CMD"
fi

PR_NUM="$(printf '%s' "${MERGE_SEG:-$CMD}" | sed -n 's/.*gh pr merge[[:space:]]\{1,\}\([0-9]\{1,\}\).*/\1/p' | head -1)"
[ -z "$PR_NUM" ] && allow   # `gh pr merge` with no number merges the current branch's PR; gh will resolve it, we cannot.

command -v gh >/dev/null 2>&1 || deny "gh is not on PATH, so the review verdict cannot be checked"
command -v jq >/dev/null 2>&1 || deny "jq is not on PATH, so the review verdict cannot be checked"

past_deadline() { [ $((SECONDS - START)) -ge "$DEADLINE_SECONDS" ]; }

# ---------------------------------------------------------------------------
# Check 1 — rule 13: the LATEST verdict must be an approval.
# `gh pr review --approve` is blocked for a same-identity author, so the repo's
# convention is a COMMENT verdict whose body states APPROVE. Both count; the
# newest verdict wins, so a later REQUEST CHANGES correctly overrides.
# ---------------------------------------------------------------------------
PR_JSON="$(gh pr view "$PR_NUM" --json reviews,comments,body 2>/dev/null)" \
  || deny "could not read PR #$PR_NUM (network or auth); refusing to merge unverified"
past_deadline && deny "the gate could not finish within ${DEADLINE_SECONDS}s — an unanalysed merge must not proceed"

VERDICT="$(printf '%s' "$PR_JSON" | jq -r '
  [ (.reviews // [])[] | {at: .submittedAt, body: (.body // "")},
    (.comments // [])[] | {at: .createdAt,  body: (.body // "")} ]
  | map(select(.body | test("APPROVE|APPROVED|REQUEST CHANGES"; "i")))
  | sort_by(.at) | last | .body // ""' 2>/dev/null)"

[ -z "$VERDICT" ] && deny "PR #$PR_NUM has no posted review verdict — rule 13 requires an independent pr-reviewer APPROVE before merge"

if printf '%s' "$VERDICT" | head -5 | grep -qiE 'REQUEST CHANGES'; then
  deny "PR #$PR_NUM's latest verdict is REQUEST CHANGES: $(printf '%s' "$VERDICT" | head -1 | cut -c1-120)"
fi
printf '%s' "$VERDICT" | head -5 | grep -qiE 'APPROVE' \
  || deny "PR #$PR_NUM's latest verdict does not state APPROVE (rule 13)"

# ---------------------------------------------------------------------------
# Check 2 — `Closes #NN` must not point at an issue with unticked criteria.
# ---------------------------------------------------------------------------
BODY="$(printf '%s' "$PR_JSON" | jq -r '.body // ""')"
CLOSES="$(printf '%s' "$BODY" | grep -oiE '(closes|fixes|resolves)[[:space:]]+#[0-9]+' | grep -oE '[0-9]+' | sort -u)"

for issue in $CLOSES; do
  past_deadline && deny "the gate could not finish within ${DEADLINE_SECONDS}s — an unanalysed merge must not proceed"
  IBODY="$(gh issue view "$issue" --json body --jq '.body // ""' 2>/dev/null)" || continue
  # Only the acceptance-criteria section; other checklists (e.g. a PR-style task
  # list) are not the contract a `Closes` decides.
  UNCHECKED="$(printf '%s' "$IBODY" \
    | awk '/^#+.*[Aa]cceptance +[Cc]riteria/{f=1;next} f&&/^#+ /{f=0} f' \
    | grep -cE '^[[:space:]]*-[[:space:]]*\[[[:space:]]\]' || true)"
  if [ "${UNCHECKED:-0}" -gt 0 ]; then
    deny "PR #$PR_NUM says it closes #$issue, but #$issue has $UNCHECKED unticked acceptance criteria. Use 'Refs #$issue' and say which criterion is unmet (rule 7/11), or tick them with what you ran."
  fi
done

exit 0
