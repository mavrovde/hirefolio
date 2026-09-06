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
# moment this repo already guards elsewhere. Within its boundary this hook
# FAILS CLOSED: anything it cannot analyse or verify is a deny, never an allow.
#
# THE BOUNDARY, stated honestly (#291 review rounds 5-7): this is a
# COMMAND-TEXT gate. It analyses the Bash tool's command string and nothing
# else, so a merge that arrives as FILE CONTENTS or through an opaque transport
# is invisible to it — measured open shapes: `cat script.sh | bash`,
# `bash script.sh`, and `ssh -o "ProxyCommand=..."`. Guarding file execution
# is the destruction guard's territory and a different analysis; pretending
# this hook covers it would be the same false comfort the heredoc comment gave
# (round 2). A further NAMED residual inside the command-text boundary: a
# quote-split command WORD — `gh pr me"rge" N` — reassembles only in the shell,
# and this gate does not model word-level concatenation (measured ALLOW; the
# accepted guard-destructive.sh carries the same residual, #291 round 8). The
# honest promise is therefore: no merge typed as a PLAINLY-SPELLED command
# slips through; an author quoting mid-word is evading, not typing.
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

# The env form only fires when the hook itself was launched with it. A caller
# writes `PR_MERGE_GATE=0 gh pr merge …`, which is a prefix on the COMMAND TEXT
# and never reaches this process — the check below (on each segment) is the one
# that actually implements the documented hatch. Keeping both costs nothing.
[ "${PR_MERGE_GATE:-1}" = "0" ] && allow

# Extract the command with jq, like both siblings. A hand-rolled sed
# over-captured on multi-line payloads and was the root of several bypasses.
INPUT="$(cat)"
CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"

# SIZE BOUND before any parsing — the sibling guard's #219/#225 lesson, which
# this gate skipped and re-learned: quote_split is a character loop, so a large
# enough command outlives the 30s hook cap (3000 segments measured 39s), and a
# timed-out PreToolUse hook does not deny. O(1) fail-closed beats O(n²) timeout.
if [ "${#CMD}" -gt 24576 ]; then
  case "$CMD" in
    *merge*) deny "command too large to analyse (${#CMD} bytes > 24576) — run the merge alone" ;;
    *) : ;;  # no merge can be hiding where the WORD never appears; stay out of big non-merge commands' way
  esac
fi
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
# A quoted argument handed to bash -c / eval / ssh is a SCRIPT: split it like
# the shell would and ask each inner command. Depth-bounded, like the sibling.
PMG_INNER_DEPTH=0
inner_script_invokes_pr_merge() {
  local body="$1" line inner found=1 OLD="$IFS"
  [ "$PMG_INNER_DEPTH" -ge 3 ] && return 0        # cannot analyse further → gate
  PMG_INNER_DEPTH=$((PMG_INNER_DEPTH + 1))
  body="${body//$NL_SENTINEL/$'\n'}"
  while IFS= read -r line; do
    [ "$found" = 0 ] && break
    IFS=$'\n'
    for inner in $(quote_split "$line"); do
      if segment_invokes_pr_merge "$inner"; then found=0; break; fi
    done
    IFS="$OLD"
  done <<< "$body"
  IFS="$OLD"
  PMG_INNER_DEPTH=$((PMG_INNER_DEPTH - 1))
  return $found
}

segment_invokes_pr_merge() {
  local seg="$1"
  # DENY, not "treat as merge" — see the twin comment in the peel loop.
  [ "$SECONDS" -ge "$INSPECT_DEADLINE" ] \
    && deny "command too large to analyse within budget — run the merge alone"
  seg="$(printf '%s' "$seg" | tr '\n\t' '  ' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+/ /g')"

  local changed=1 loops=0
  while [ "$changed" = "1" ] && [ "$loops" -lt 8 ]; do
    changed=0; loops=$((loops + 1))
    # DENY outright, not "treat as merge": returning 0 here sent an empty
    # operand into verification, which falls back to the CURRENT branch's PR —
    # a timeout could have allowed a merge by verifying the wrong PR (#291 r7).
    [ "$SECONDS" -ge "$INSPECT_DEADLINE" ] \
      && deny "command too large to analyse within budget — run the merge alone"
    [ "${seg:0:1}" = '\' ] && { seg="${seg#\\}"; changed=1; }
    case "$seg" in
      "do "*|"then "*|"else "*|"elif "*|"{ "*|"( "*) seg="${seg#* }"; changed=1 ;;
    esac
    # The documented bypass lives HERE, not in the hook's own environment: a
    # caller types `PR_MERGE_GATE=0 gh pr merge 291`, so the token is part of
    # the command text and the strip below would eat it unread. Same regex and
    # same position as guard-destructive.sh:242 — one model, two hooks (#237).
    if printf '%s' "$seg" | grep -Eq '^([A-Za-z_][A-Za-z0-9_]*=[^ ]* )*PR_MERGE_GATE=0( |$)'; then
      return 1   # authorized: this segment is not gated
    fi
    while [[ "$seg" =~ ^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+ ]]; do
      seg="${seg#* }"; changed=1
    done
    if command -v peel_wrapper >/dev/null 2>&1; then
      PEEL_RESULT=""
      if peel_wrapper "$seg" && [ -n "${PEEL_RESULT:-}" ] && [ "$PEEL_RESULT" != "$seg" ]; then
        seg="$PEEL_RESULT"; changed=1
      fi
    fi
    # `xargs [opts] gh pr merge` — same one-pass strip as the siblings (#219).
    # The operand arrives on STDIN, so which PR this merges is unknowable here:
    # record that, and fail closed below rather than silently checking whichever
    # PR the current branch happens to have.
    if printf '%s' "$seg" | grep -Eq '^xargs( |$)'; then
      seg="$(printf '%s' "$seg" | sed -E 's/^xargs +//; s/^((-[^ ]+|\{\}|[A-Za-z]=) )*//')"
      MERGE_OPERAND_UNKNOWABLE=1
      changed=1
    fi
  done

  # `bash -c "…"` / `sh -lc '…'` / `eval …` / `ssh host "…"`: the argument is a
  # SCRIPT, and a merge inside it is a real merge. Same patterns the pre-push
  # gate uses (#291 review round 2 proved all four were open here).
  if printf '%s' "$seg" | grep -Eq '^(bash|sh|zsh|dash) +((-o [^ ]+|-[A-Za-z]+|--[A-Za-z-]+) +)*-[A-Za-z]*c[A-Za-z]* (-- +)?'; then
    seg="$(printf '%s' "$seg" | sed -E "s/^(bash|sh|zsh|dash) +((-o [^ ]+|-[A-Za-z]+|--[A-Za-z-]+) +)*-[A-Za-z]*c[A-Za-z]* +(-- +)?//; s/^\\\$?[\"']//; s/[\"']$//")"
    inner_script_invokes_pr_merge "$seg" && return 0
    return 1
  elif printf '%s' "$seg" | grep -Eq '^eval '; then
    seg="$(printf '%s' "$seg" | sed -E "s/^eval +//; s/^\\\$?[\"']//; s/[\"']$//")"
    inner_script_invokes_pr_merge "$seg" && return 0
    return 1
  elif printf '%s' "$seg" | grep -Eq '^ssh '; then
    # A merge on the remote end merges all the same. Inspect the WHOLE remainder
    # first — protection independent of getting ssh's option grammar right —
    # then walk options and the host off the front so a bare
    # `ssh box gh pr merge N` is seen as the command it is. Handing the raw
    # remainder to the recursion was DEAD CODE: its command word was the host.
    local sshrest="${seg#ssh }" sshflag
    inner_script_invokes_pr_merge "$sshrest" && return 0
    while [ "${sshrest:0:1}" = "-" ]; do
      sshflag="${sshrest%% *}"
      [ "$sshflag" = "$sshrest" ] && break
      sshrest="${sshrest#* }"
      case "$sshflag" in
        # A value-taking letter LAST in a cluster still consumes the next word:
        # `-tp 22` is `-t -p 22`. Matching only `-p` missed `-tp` and read the
        # port as the host.
        -*[bcDEeFIiJLlmOopQRSWw]) sshrest="${sshrest#* }" ;;
      esac
    done
    sshrest="${sshrest#* }"                                    # drop [user@]host
    sshrest="$(printf '%s' "$sshrest" | sed -E "s/^\\\$?[\"']//; s/[\"']$//")"
    inner_script_invokes_pr_merge "$sshrest" && return 0
    return 1
  fi

  # Command word must be `gh`, then the subcommand pair `pr merge` — with gh's
  # value-taking globals consumed in between, so `gh --repo x pr merge 1` is
  # caught exactly like `gh pr merge 1 --repo x`.
  # IFS is $'\n' in the caller's loop, so a bare `set -- $seg` would NOT split
  # on spaces and the whole segment would arrive as one positional parameter —
  # every wrapper and compound case then reads as "not a merge" and the gate
  # allows. Restore word splitting locally.
  # Cheap reject before the O(n) split: the deadline exists because cost is a
  # security property here (#219), and most segments are not merges.
  case "$seg" in *merge*) ;; *) return 1 ;; esac
  argv_split "$seg"
  # A quoted value with a NEWLINE arrives here cut at the line boundary, so the
  # operand after it is missing from this argv. Mark the target unknowable —
  # the deny below — instead of walking a truncated argv and falling back to
  # the current branch's PR (round 5's wrong-PR-allow, one line later).
  [ "${ARGV_SPLIT_UNTERMINATED:-0}" = "1" ] && MERGE_OPERAND_UNKNOWABLE=1
  [ "${#ARGV_SPLIT_RESULT[@]}" -eq 0 ] && return 1
  set -- "${ARGV_SPLIT_RESULT[@]}"
  [ "${1:-}" = "gh" ] || return 1
  shift || return 1
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
  shift
  # The operand may sit after flags (`gh pr merge --squash 291`) or be absent
  # (merge the current branch's PR). Walk the rest the same way, consuming
  # value-taking merge flags, and keep the FIRST bare operand.
  MERGE_OPERAND=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -b|--body|-t|--subject|-F|--body-file|-A|--author-email|-R|--repo|--match-head-commit) \
        shift; shift || break ;;
      -*) shift ;;
      *) MERGE_OPERAND="$1"; break ;;
    esac
  done
  return 0
}

MERGE_SEG=""
MERGE_OPERAND=""
MERGE_OPERAND_UNKNOWABLE=0
MERGE_OPERANDS=()
MERGE_UNKNOWABLE=()
OLD_IFS="$IFS"
IN_HEREDOC_DELIM=""
while IFS= read -r line; do
  # HEREDOC BODIES ARE DATA, NOT COMMANDS. A commit message, a PR body or a
  # review quoted through `git commit -F -`/`gh pr create --body-file` routinely
  # contains the literal text `gh pr merge` — and this gate blocked its own
  # commit that way before this branch existed. The shared lib already models
  # heredocs for exactly this reason (#212/#237); skip a body until its
  # delimiter.
  if [ -n "$IN_HEREDOC_DELIM" ]; then
    trimmed="${line#"${line%%[![:space:]]*}"}"
    [ "$trimmed" = "$IN_HEREDOC_DELIM" ] && IN_HEREDOC_DELIM=""
    continue
  fi
  delim="$(heredoc_delim "$line" 2>/dev/null || true)"
  # ONLY a text-tool heredoc is data. `bash <<'EOF' … gh pr merge N … EOF` is a
  # script the shell EXECUTES, and skipping every heredoc body unconditionally
  # was a live bypass (#291 review round 2) — an earlier comment here argued a
  # merge inside one "is not reachable"; it was, and that rationale is deleted
  # rather than left as an invitation to revert this. `line_is_all_text_tools`
  # is the shared lib's answer to exactly this question (#204/#212): the body is
  # dropped only when every command on the opening line is a text tool.
  if [ -n "$delim" ] && line_is_all_text_tools "$line"; then
    IN_HEREDOC_DELIM="$delim"
  fi
  [ "$SECONDS" -ge "$INSPECT_DEADLINE" ] \
    && deny "command too large to analyse within budget — run the merge alone"
  IFS=$'\n'
  for seg in $(quote_split "$line"); do
    # EVERY merge, not just the last. `gh pr merge 284 && gh pr merge 999`
    # previously kept only the second and let the first through unverified,
    # which contradicted this file's own "never an allow" promise (#291 r5).
    # Per-SEGMENT deadline too: one line can carry thousands of segments
    # (measured: 3000 took 39s, past the 30s hook cap — and a timed-out
    # PreToolUse hook does not deny, #219). Better a false deny on a monster
    # command than a silent timeout-allow.
    [ "$SECONDS" -ge "$INSPECT_DEADLINE" ] \
      && deny "command too large to analyse within budget — run the merge alone"
    MERGE_OPERAND_UNKNOWABLE=0   # per-segment: `ls | xargs rm` must not taint a later merge
    if segment_invokes_pr_merge "$seg"; then
      MERGE_SEG="$seg"
      MERGE_OPERANDS+=("$MERGE_OPERAND")
      MERGE_UNKNOWABLE+=("$MERGE_OPERAND_UNKNOWABLE")
      MERGE_OPERAND=""; MERGE_OPERAND_UNKNOWABLE=0
    fi
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
# MERGE_OPERAND comes from the argv walk, so flags before the number are handled
# (`gh pr merge --squash 291` previously fell through and checked the CURRENT
# branch's PR — a live bypass found in review round 2). A URL operand is
# normalised to its number.
for MERGE_IDX in "${!MERGE_OPERANDS[@]}"; do
MERGE_OPERAND="${MERGE_OPERANDS[$MERGE_IDX]}"
MERGE_OPERAND_UNKNOWABLE="${MERGE_UNKNOWABLE[$MERGE_IDX]}"
[ "${MERGE_OPERAND_UNKNOWABLE:-0}" = "1" ] && deny "the PR this merges cannot be determined from the command (stdin operand, or a quoted value spanning lines) — run the merge alone with an explicit PR number"

# ONE normalisation path for the operand. Two overlapping blocks lived here
# briefly and the second silently rescued what the first dropped, which made the
# "operand ignored" mutation EQUIVALENT — it survived, and a survivor is a
# finding about the code, not a gap to paper over (§33). Strip the quotes once,
# then: a number, a pull URL, or a branch gh can resolve.
PR_NUM=""
if [ -n "${MERGE_OPERAND:-}" ]; then
  # No quote-stripping here: argv_split already removed them AT THE SPLIT,
  # which is the only place it is safe (a strip afterwards forged PR numbers).
  UNQUOTED="$MERGE_OPERAND"
  PR_NUM="$(printf '%s' "$UNQUOTED" \
    | sed -E 's#^https?://[^ ]*/pull/([0-9]+)/?$#\1#' \
    | grep -oE '^[0-9]+$' || true)"
  # `gh pr merge` also accepts a BRANCH; ask gh rather than guess at naming.
  # An unexpanded `$VAR` this hook cannot evaluate is left for the deny below.
  if [ -z "$PR_NUM" ] && [ "${UNQUOTED#*\$}" = "$UNQUOTED" ]; then
    PR_NUM="$(gh pr view "$UNQUOTED" --json number --jq '.number' 2>/dev/null | grep -oE '^[0-9]+$' || true)"
  fi
fi

# Still unreadable — e.g. a quoted flag value that word-split
# (`gh pr merge -b "squash msg" 291`), or an unexpanded `$PR` this hook cannot
# evaluate. Falling back to the current branch would verify a DIFFERENT PR and
# allow the merge (round-2 blocker 3 one level deeper), so refuse instead. The
# `PR_MERGE_GATE=0` prefix is a real escape now that it works.
if [ -n "${MERGE_OPERAND:-}" ] && [ -z "$PR_NUM" ]; then
  deny "could not resolve '${MERGE_OPERAND}' to a pull request — pass an explicit PR number, or prefix PR_MERGE_GATE=0 if this merge is already authorized"
fi
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

# MESSAGE-ONLY, and deliberately so (#291 review round 2, the #240 answer). An
# empty verdict also yields an empty FIRST_MARKER, so the APPROVE check below
# denies anyway — the two are behaviourally equivalent for every input the jq
# filter admits, and no test can distinguish them. This line exists because
# "no posted review verdict" tells the author what to DO, where "does not state
# APPROVE" would not. It is therefore NOT in the mutation contract: writing a
# case that cannot fail is worse than documenting the equivalence.
[ -z "$VERDICT" ] && deny "PR #$PR_NUM has no posted review verdict — rule 13 requires an independent pr-reviewer APPROVE before merge"

# The verdict is whichever marker appears FIRST — that is the heading. A body
# that approves and then quotes the round it supersedes ("the REQUEST CHANGES
# findings are fixed") must not flip to deny; review threads do this routinely,
# including the one that found this. A fixed head -N window got it wrong
# whenever the quote landed inside the window.
FIRST_MARKER="$(printf '%s' "$VERDICT" | grep -oiE 'REQUEST CHANGES|APPROVED?' | head -1)"

# ONE check is load-bearing here: the APPROVE requirement below. The two denies
# that precede it (empty verdict, explicit REQUEST CHANGES) are MESSAGE-ONLY —
# an empty verdict yields an empty marker, and a REQUEST-CHANGES marker fails
# the APPROVE test, so deleting either changes no decision for any input the jq
# filter admits. Both were mutation-tested and SURVIVED; rather than dress that
# up with cases that cannot fail, the equivalence is documented here (the #240
# answer, applied to my own gate). They earn their place by telling the author
# what to DO — "no posted review verdict" and "fix the findings in this PR
# first" are actionable where "does not state APPROVE" is not.
if printf '%s' "$FIRST_MARKER" | grep -qiE 'REQUEST CHANGES'; then
  deny "PR #$PR_NUM's latest verdict is REQUEST CHANGES — fix the findings in this PR first (rule 11)"
fi
printf '%s' "$FIRST_MARKER" | grep -qiE 'APPROVE' \
  || deny "PR #$PR_NUM's latest verdict does not state APPROVE (rule 13)"

# --- Check 2: `Closes #NN` must not point at unticked criteria ---------------
BODY="$(printf '%s' "$PR_JSON" | jq -r '.body // ""')"
CLOSES="$(printf '%s' "$BODY" | grep -oiE '(closes|fixes|resolves)[[:space:]]+#[0-9]+' | grep -oE '[0-9]+' | sort -u)"

for issue in $CLOSES; do
  past_deadline && deny "could not finish within ${DEADLINE_SECONDS}s — an unanalysed merge must not proceed"
  # FAIL CLOSED: an unreadable issue is not evidence that its criteria are met.
  IBODY="$(gh issue view "$issue" --json body --jq '.body // ""' 2>/dev/null)" \
    || deny "PR #$PR_NUM says it closes #$issue but that issue could not be read — refusing to close an issue whose criteria are unverified"
  # Heading match is `#`-anchored and tolerates all-caps; a **bold** pseudo-heading
  # is NOT matched (measured) — the issue template always uses a real heading.
  # BWK-awk portable: no IGNORECASE (macOS ships BWK awk).
  UNCHECKED="$(printf '%s' "$IBODY" \
    | awk '/^#+.*([Aa]cceptance|ACCEPTANCE).*([Cc]riteria|CRITERIA)/{f=1;next} f&&/^#+ /{f=0} f' \
    | grep -cE '^[[:space:]]*[-*][[:space:]]*\[[[:space:]]\]' || true)"
  if [ "${UNCHECKED:-0}" -gt 0 ]; then
    deny "PR #$PR_NUM says it closes #$issue, but #$issue has $UNCHECKED unticked acceptance criteria — use 'Refs #$issue' and name the unmet criterion, or tick them with what you ran"
  fi
done

done   # every merge in this command has now been verified

exit 0
