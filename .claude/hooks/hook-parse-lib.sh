#!/usr/bin/env bash
# hook-parse-lib.sh — the ONE shell-command parsing model shared by this repo's
# PreToolUse hooks (issue #237; lessons-learned §21.12: two functions jointly
# enforcing an invariant must share one model of the input).
#
# Extracted VERBATIM from guard-destructive.sh (#204→#225 lineage): quote-aware
# segmentation, the transparent-wrapper peel, and the text-tool heredoc
# exemption. Both `guard-destructive.sh` (rule 9) and `pre-push-tests.sh`
# (rule 3) source this file, so "is this text a COMMAND or quoted DATA?" has a
# single answer — a fix or a hole in one hook cannot silently diverge from the
# other.
#
# Contract for sourcing hooks:
#   - functions here read $SECONDS against $INSPECT_DEADLINE (set it first;
#     past the budget they fail CLOSED — bodies stay inspected);
#   - set LC_ALL=C and `set -f` before calling (byte-wise scanning, #219; no
#     pathname expansion of segments);
#   - this file only defines functions/constants — it reads no stdin, writes
#     no stdout, and never exits.

# Text/VCS tools: if a segment's command is one of these, any destructive-looking
# text in it is an ARGUMENT (message, search pattern, echoed string), not an
# invocation — skip the segment.
is_text_tool() {
  case "$1" in
    git|echo|printf|grep|egrep|fgrep|rg|ag|cat|bat|less|more|head|tail|sed|awk|\
    tee|diff|comm|sort|uniq|cut|tr|jq|yq|wc|nl|column|fold|pr|strings|xxd|hexdump|\
    curl|wget|man|help|history|alias|true|false|:|test|\[) return 0 ;;
    *) return 1 ;;
  esac
}

# Stand-in for a newline that appeared INSIDE quotes. Chosen as a control
# character so it can never occur in a real command and is not whitespace, which
# keeps it intact through the space-collapsing normaliser below.
NL_SENTINEL=$'\x01'

# Quote-state marker for an open ANSI-C $'…' region. A control character for the
# same reason as NL_SENTINEL: the round-1 review of #213 showed the in-band
# marker "A" let a literal uppercase A inside $'…' close the region early --
# `bash -c $'echo DONE A\n<destroy>'` was allowed and prose with an A denied.
ANSI_Q=$'\x02'

# Transparent wrappers (#217): commands that run the command following them
# unchanged. ONE list, used by both inspect_segment's unwrap loop and
# pipes_into_shell, so the two cannot disagree about what a wrapper is (§21: two
# functions jointly enforcing an invariant must share one model of the input).
# The shell executes an effect, not a framing — every wrapper missing here is a
# bypass — so this list errs long: anything that merely re-nices, re-buffers,
# times, or re-users its argv belongs in it.
#
# Returns 0 when the first word was a wrapper, with the peeled remainder in
# PEEL_RESULT; consumes its options, the separate-token VALUES of value-taking
# flags (`nice -n 10`, `timeout -k 5`, `sudo -u root`), and the bare operand of
# duration/priority/mask-taking wrappers (`timeout 60`, `chrt 50`,
# `taskset 0x1`). A joined value (`-n10`, `-o0`, `-c3`) needs no extra token.
# Value flags are per-wrapper, not shared: consuming a value after a flag that
# does not take one (`env -i`) would swallow the real command — a false ALLOW.
#
# The result comes back in PEEL_RESULT (a global), NOT on stdout: a command
# substitution forks a subshell, and this runs per segment — on a many-segment
# command those forks alone outlived the hook timeout, and a hook that times out
# does not deny, so the cost was itself a bypass (#235). Every caller must read
# PEEL_RESULT; `$(peel_wrapper …)` now yields the empty string.
peel_wrapper() {
  local seg="$1" w rest tok valflags=""
  PEEL_RESULT=""
  w="${seg%% *}"
  [ "$w" = "$seg" ] && return 1          # bare word — nothing follows to run
  case "$w" in
    busybox) PEEL_RESULT="${seg#busybox }"; return 0 ;;  # applet name follows
    sudo|doas|command|nohup|time|exec|env|nice|ionice|stdbuf|setsid|chrt|taskset|timeout) ;;
    *) return 1 ;;
  esac
  rest="${seg#* }"
  case "$w" in
    sudo)    valflags='-u|-g|-p|-C|-D|-U|-R|-T' ;;
    doas)    valflags='-u|-C|-a' ;;
    exec)    valflags='-a' ;;
    # env's -S splits its value into argv and PREPENDS it -- the value IS the
    # command (round-1 review: `env -S <destroy>` was allowed because -S ate
    # the command word as its value). -u/-C take true values.
    env)     valflags='-u|-C' ;;
    nice)    valflags='-n|--adjustment' ;;
    ionice)  valflags='-c|-n|-t|-p' ;;
    stdbuf)  valflags='-i|-o|-e' ;;
    timeout) valflags='-k|-s|--kill-after|--signal' ;;
  esac
  while [ "${rest:0:1}" = "-" ]; do
    tok="${rest%% *}"
    [ "$tok" = "$rest" ] && { rest=""; break; }
    rest="${rest#* }"
    if [ -n "$valflags" ] && [[ "$tok" =~ ^($valflags)$ ]]; then
      case "$rest" in *" "*) rest="${rest#* }" ;; *) rest="" ;; esac
    fi
  done
  case "$w" in
    timeout|chrt|taskset)
      tok="${rest%% *}"
      if [ "$tok" != "$rest" ] && printf '%s' "$tok" | grep -Eq '^(0x)?[0-9][0-9a-fA-F.,:smhd-]*$'; then
        rest="${rest#* }"
      fi ;;
  esac
  PEEL_RESULT="$rest"
  return 0
}

# QUOTE-AWARE segmentation: split the command into segments on shell separators
# (; | & newline and subshell/substitution boundaries ( ) ` ) but ONLY when they
# occur OUTSIDE single/double quotes. This is what makes the guard robust in both
# directions: a real unquoted pipe (`cat list | xargs docker volume rm`) is split
# and each part inspected, while a separator appearing INSIDE a quoted argument
# (a `git commit -m "...| xargs docker volume rm..."` message) stays part of that
# one git-led segment and is correctly treated as text, not an invocation.
quote_split() {
  local s="$1" out="" i c nx q="" n=${#1}
  for (( i=0; i<n; i++ )); do
    c="${s:i:1}"
    # A backslash escapes the next character everywhere except inside single
    # quotes. This MUST match mask_quotes exactly: those two functions jointly
    # grant the heredoc exemption, and when they disagreed about what a line was,
    # an ordinary `git commit -m "the \" char" ; bash <<'EOF'` looked like an
    # unclosed quote to one and a real redirect to the other — so the line read as
    # "all text tools" and the shell heredoc behind it was exempted.
    if [ "$c" = '\' ] && [ "$q" != "'" ] && [ $((i + 1)) -lt "$n" ]; then
      nx="${s:i+1:1}"
      if [ -n "$q" ] && [ "$nx" = $'\n' ]; then out+="$NL_SENTINEL"
      # Inside ANSI-C quoting, `\n` EXPANDS to a newline before the shell runs
      # the text — for a body handed to a shell that newline is a command
      # separator, so it gets the same sentinel treatment as a real quoted
      # newline. Leaving it as the two literal characters hid the second command
      # of `bash -c $'echo hi\n<destroy>'` behind a benign first token (#213).
      elif [ "$q" = "$ANSI_Q" ] && [ "$nx" = "n" ]; then out+="$NL_SENTINEL"
      else out+="$c$nx"; fi
      i=$((i + 1)); continue
    fi
    if [ -n "$q" ]; then
      # INSIDE quotes a newline is DATA, not a separator, so it must not end the
      # segment — otherwise a line of prose that merely *starts* with a
      # destructive verb gets inspected as an invocation, which is #204.
      #
      # But a quoted newline is not always data: `bash -c "echo hi\n<destroy>"`
      # is a two-command script, and flattening it to one segment would hide the
      # second command behind a benign first token. So the newline is replaced
      # with a SENTINEL that is neither a separator nor whitespace. Segments that
      # turn out to be executed as shell code restore it (see restore_newlines);
      # everything else flattens it to a space and treats it as prose.
      if [ "$c" = $'\n' ]; then out+="$NL_SENTINEL"; else out+="$c"; fi
      if [ "$c" = "$q" ] || { [ "$q" = "$ANSI_Q" ] && [ "$c" = "'" ]; }; then q=""; fi
      continue
    fi
    # ANSI-C quoting $'…' is a THIRD quoting model (#213): quoted text whose
    # backslash rules differ from both '…' and "…" — in particular \' is an
    # escaped quote INSIDE the region, not a terminator. Tracked with q=$ANSI_Q
    # (never a real input character) so the backslash branch above stays active
    # while the plain-single-quote rule (backslash is literal) does not.
    if [ "$c" = '$' ] && [ $((i + 1)) -lt "$n" ] && [ "${s:i+1:1}" = "'" ]; then
      q="$ANSI_Q"; out+="\$'"; i=$((i + 1)); continue
    fi
    case "$c" in
      \'|\") q="$c"; out+="$c" ;;
      '|'|';'|'&'|'('|')'|'`'|$'\n') out+=$'\n' ;;
      *) out+="$c" ;;
    esac
  done
  # An UNTERMINATED quote means we never really knew where the data ended, so the
  # protection above was based on a guess. Fall back to treating those newlines
  # as separators — the conservative direction.
  [ -n "$q" ] && out="${out//$NL_SENTINEL/$'\n'}"
  printf '%s' "$out"
}

# Blank out quoted regions, preserving length, so a `<<` that is merely part of a
# quoted STRING is not mistaken for a redirect. Offsets in the masked line map
# 1:1 onto the original, which is how the delimiter is recovered below.
mask_quotes() {
  local s="$1" out="" i c q="" n=${#1}
  for (( i=0; i<n; i++ )); do
    c="${s:i:1}"
    # A backslash escapes the next character everywhere EXCEPT inside single
    # quotes, where it is literal. Without this, `echo "a \" <<EOF"` looks like
    # the quote closed early, the `<<EOF` reads as a real redirect, and a line of
    # pure text can open a heredoc that swallows the commands after it.
    if [ "$c" = '\' ] && [ "$q" != "'" ] && [ $((i + 1)) -lt "$n" ]; then
      out+="  "; i=$((i + 1)); continue
    fi
    if [ -n "$q" ]; then
      out+=" "
      if [ "$c" = "$q" ] || { [ "$q" = "$ANSI_Q" ] && [ "$c" = "'" ]; }; then q=""; fi
      continue
    fi
    # ANSI-C quoting $'…' — same third quoting model as in quote_split (#213);
    # the two functions must share one model or the heredoc exemption misfires.
    if [ "$c" = '$' ] && [ $((i + 1)) -lt "$n" ] && [ "${s:i+1:1}" = "'" ]; then
      q="$ANSI_Q"; out+="  "; i=$((i + 1)); continue
    fi
    # An unquoted `#` at the start of a word begins a comment: the rest of the
    # line is not code, so a `<<EOF` in it never opens a heredoc. Treating it as
    # one would let `echo ok # <<EOF` swallow the real command on the next line.
    if [ "$c" = "#" ] && { [ "$i" -eq 0 ] || [[ "${s:i-1:1}" =~ [[:space:]] ]]; }; then
      while [ "$i" -lt "$n" ]; do out+=" "; i=$((i + 1)); done
      break
    fi
    case "$c" in
      \'|\") q="$c"; out+=" " ;;
      *) out+="$c" ;;
    esac
  done
  printf '%s' "$out"
}

# Heredoc delimiter opened by this line, or empty. Reported ONLY for a heredoc
# whose body the shell will NOT expand — i.e. a QUOTED (or backslash-escaped)
# delimiter, `<<'EOF'` / `<<"EOF"` / `<<\EOF`, and outside quotes, and not a
# here-string (`<<<`).
#
# The quoting matters and is not a formality: with an UNQUOTED delimiter the
# shell expands the body, so `$(…)` and backticks in it EXECUTE. Such a body is
# code wearing a document's clothes and must stay inspected — reporting a
# delimiter here would exempt it.
# Split a command segment into ARGV the way the shell does: on UNQUOTED
# whitespace, with a quoted run kept as ONE token and its quotes removed.
# Result lands in the ARGV_SPLIT_RESULT array — an array, not a string list,
# because a token can legitimately contain a newline.
#
# This exists because `set -- $seg` (IFS word-splitting) is NOT argv splitting
# and cannot be made into it. `gh pr merge -b "squash 999" 284` splits into
# `-b` `"squash` `999"` `284`, so a merge gate reading the operand positionally
# saw `999"` — and a `sed` that stripped the stray quote turned it into a valid
# PR number, verifying PR 999 while merging 284 (#291 review round 5). Quoting
# must be modelled where the split happens, never patched afterwards.
#
# Same three quoting models as mask_quotes/quote_split — plain single, double,
# and ANSI-C `$'…'` — plus backslash escapes outside single quotes. The three
# functions must agree; #213 and #237 both came from them drifting apart.
argv_split() {
  local s="$1" n=${#1} i c q="" tok="" started=0
  ARGV_SPLIT_RESULT=()
  for (( i=0; i<n; i++ )); do
    c="${s:i:1}"
    if [ "$c" = '\' ] && [ "$q" != "'" ] && [ $((i + 1)) -lt "$n" ]; then
      tok+="${s:i+1:1}"; started=1; i=$((i + 1)); continue
    fi
    if [ -n "$q" ]; then
      if [ "$c" = "$q" ] || { [ "$q" = "$ANSI_Q" ] && [ "$c" = "'" ]; }; then q=""
      else tok+="$c"; fi
      continue
    fi
    if [ "$c" = '$' ] && [ $((i + 1)) -lt "$n" ] && [ "${s:i+1:1}" = "'" ]; then
      q="$ANSI_Q"; started=1; i=$((i + 1)); continue
    fi
    case "$c" in
      \'|\") q="$c"; started=1 ;;
      ' '|$'\t'|$'\n')
        if [ "$started" = "1" ]; then ARGV_SPLIT_RESULT+=("$tok"); tok=""; started=0; fi ;;
      *) tok+="$c"; started=1 ;;
    esac
  done
  [ "$started" = "1" ] && ARGV_SPLIT_RESULT+=("$tok")
  return 0
}

heredoc_delim() {
  local line="$1" masked head rest
  # Cheap reject FIRST. mask_quotes is an O(n) character loop and this runs per
  # line, so scanning every line of a large command doubled the guard's cost —
  # and a PreToolUse hook that times out does NOT deny, so the input size at
  # which the guard stops guarding was effectively halved. Masking can only blank
  # characters, never introduce a `<<`, so a raw line without one cannot yield a
  # heredoc.
  case "$line" in *'<<'*) ;; *) return 0 ;; esac
  masked="$(mask_quotes "$line")"
  case "$masked" in *"<<"*) ;; *) return 0 ;; esac
  head="${masked%%<<*}"
  rest="${line:${#head}}"                 # original text from the `<<` onwards
  [ "${rest:2:1}" = "<" ] && return 0     # here-string, not a heredoc
  printf '%s' "$rest" |
    sed -nE "s/^<<-?[[:space:]]*(\"([A-Za-z_][A-Za-z0-9_]*)\"|'([A-Za-z_][A-Za-z0-9_]*)'|\\\\([A-Za-z_][A-Za-z0-9_]*)).*/\2\3\4/p"
}

# The files a text-tool heredoc line writes to, one per output line (#212):
# EVERY `>`/`>>` redirect operand (a `2>err.log` alongside `> s.sh` must not
# hide the script — review round 1) plus a `tee` operand. Quotes are DROPPED,
# not masked, so `cat > 's.sh'` still names its target; over-extraction from
# prose quotes only ever ADDS candidates, which keeps bodies inspected more
# often — the fail-closed direction. The heredoc word itself is removed rather
# than truncating at `<<`, so `cat <<'EOF' > s.sh` (redirect AFTER the heredoc
# word) is seen too.
heredoc_write_target() {
  local line="$1" noq
  noq="$(printf '%s' "$line" | tr -d "\"'" | sed -E 's/<<-?\\?[A-Za-z_][A-Za-z0-9_]*//g')"
  printf '%s' "$noq" | grep -oE '[0-9]*>{1,2} *[^ >]+' | sed -E 's/^[0-9]*>{1,2} *//'
  if printf '%s' "$noq" | grep -Eq '(^|[ |;&])tee '; then
    printf '%s\n' "$(printf '%s' "$noq" | sed -E 's/^.*(^|[ |;&])tee +(-[^ ]+ +)*([^ >]+).*$/\3/')"
  fi
}

# Does any line OUTSIDE the heredoc body execute one of the files it wrote?
# (#212) Covered spellings: `bash t` / `sh t` / `zsh t` / `dash t` /
# `source t` / `. t` / `exec t`, a path-execution `./t` (any prefix), and a
# `chmod` that touches it — chmod'ing the file you just wrote is the
# execute-next tell. Matching errs wide deliberately: a hit only means the body
# STAYS INSPECTED, which is the fail-closed direction; prose bodies stay exempt
# because the document they write is never executed.
#
# COST DISCIPLINE (round-1 review of this fix): the first version forked up to
# three greps per line per heredoc — O(heredocs × lines) subprocess spawns,
# 27 s on a 2.2 KB command of 50 heredoc blocks, which is past the 15 s hook
# timeout, i.e. the #219 bypass reintroduced by the #212 fix. Now the
# out-of-body lines are joined ONCE per heredoc and each target costs one grep
# over that text; and this runs BEFORE inspect_segment's deadline can see
# anything, so the budget is checked here too — past it we DENY outright.
#
# Reads the caller's `lines`/`n` via bash's dynamic scoping — the body was
# delimited against exactly that array, so re-deriving it here could disagree.
heredoc_target_executed() {
  local tgts="$1" open="$2" close="$3" b besc j others="" tgt
  # Past the budget: report "executed" so the body STAYS INSPECTED — the
  # inspection pass then trips inspect_segment's deadline check, which denies.
  # deny() must not be called here: this runs inside a command substitution,
  # where its JSON is captured into a variable and its exit kills only the
  # subshell — a deny that fails OPEN (round-2 review).
  if [ "$SECONDS" -ge "$INSPECT_DEADLINE" ]; then
    return 0
  fi
  for (( j=0; j<n; j++ )); do
    [ "$j" -ge "$open" ] && [ "$j" -le "$close" ] && continue
    others+="${lines[j]}"$'\n'
  done
  while IFS= read -r tgt; do
    [ -z "$tgt" ] && continue
    b="${tgt##*/}"
    [ -z "$b" ] && continue
    case "$others" in *"$b"*) ;; *) continue ;; esac   # cheap reject first
    besc="$(printf '%s' "$b" | sed -E 's/[][^$.*/\\+?(){}|]/\\&/g')"
    # Command-position aware, like the guard itself (header, #204): the
    # interpreter/path/chmod must sit at line start or right after a real
    # separator — a bare space before them means ARGUMENT position, which is
    # how `git add . notes.md` once read as dot-sourcing (round-2 review).
    # chmod counts only when the mode actually adds execute (`+x`/`u+x`/octal
    # with an odd digit) — `chmod 644 notes.md` is document housekeeping.
    if printf '%s' "$others" | grep -Eq "(^|[;&|()] *)((bash|sh|zsh|dash|source|exec|\.) +([^;&|]* )?([^ ;&|]*/)?$besc|chmod +(-[A-Za-z]+ +)*([ugoa]*[+=][rwstugo]*x[rwstugo]*|[0-7]*[1357][0-7]*) +[^;&|]*$besc|\.{0,2}/([^ ;&|]*/)*$besc)( |\$|;)"; then
      return 0
    fi
  done <<< "$tgts"
  return 1
}

# True only when EVERY command on the line is a text tool. The heredoc is
# consumed by the LAST command in the line, so checking the first token alone
# lets `echo hi && bash <<'EOF'` masquerade as a document — the same
# benign-first-token hole this guard keeps growing back.
line_is_all_text_tools() {
  local line="$1" part first found=0 OLD="$IFS"
  IFS=$'\n'
  for part in $(quote_split "$line"); do
    part="$(printf '%s' "$part" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+/ /g')"
    [ -z "$part" ] && continue
    found=1
    first="${part%% *}"
    if ! is_text_tool "$first"; then IFS="$OLD"; return 1; fi
  done
  IFS="$OLD"
  [ "$found" = "1" ]
}

# A heredoc fed to a TEXT tool is a document being written, not a script being
# run: `cat > notes.md <<'EOF' … EOF`. Its body must not be inspected, or writing
# documentation about a destructive command is blocked — the #204 symptom, and
# the reason this guard kept firing on notes about itself.
#
# Everything here fails CLOSED. The body is dropped only when all three hold:
#   1. the `<<` is a real redirect — outside quotes, and not `<<<`;
#   2. EVERY command on the opening line is a text tool (so `… && bash <<'EOF'`
#      and `cat f | bash <<'EOF'` keep their bodies);
#   3. the terminator actually appears later — otherwise "skip to the end" would
#      swallow the rest of the command, including anything destructive in it.
# Any doubt on any of the three and the body stays fully inspected.
strip_text_heredocs() {
  local input="$1" out="" line delim i j n end _t
  local -a lines=()
  while IFS= read -r line; do lines+=("$line"); done <<< "$input"
  n=${#lines[@]}
  for (( i=0; i<n; i++ )); do
    line="${lines[i]}"
    out+="$line"$'\n'

    delim="$(heredoc_delim "$line")"
    [ -z "$delim" ] && continue
    line_is_all_text_tools "$line" || continue

    # Budget check: this loop used to fork a sed PER LINE looking for the
    # terminator, which on a command full of unterminated heredocs was
    # O(lines^2) subprocess spawns — 52 s on a 3.8 KB command (round-2 review),
    # i.e. the #219 bypass again. The strip is now pure bash, and past the
    # budget we stop stripping and hand the rest through UNstripped: the full
    # inspection pass then hits inspect_segment's own deadline check, which
    # DENIES — fail closed without ever calling deny() from inside a command
    # substitution (where its output would be captured and its exit would kill
    # only the subshell — the round-2 "deny fails open" finding).
    if [ "$SECONDS" -ge "$INSPECT_DEADLINE" ]; then
      for (( j=i+1; j<n; j++ )); do out+="${lines[j]}"$'\n'; done
      break
    fi
    end=-1
    for (( j=i+1; j<n; j++ )); do
      _t="${lines[j]}"
      _t="${_t#"${_t%%[![:space:]]*}"}"    # ltrim without a fork
      if [ "$_t" = "$delim" ]; then
        end=$j; break
      fi
    done
    [ "$end" -lt 0 ] && continue   # no terminator: strip nothing

    # A "document" the SAME command then executes is a script (#212): all four
    # exemption conditions hold for `cat > s.sh <<'EOF' … EOF` + `bash s.sh`,
    # yet the body runs. When the write target is later executed, keep the body
    # fully inspected instead of stripping it.
    local _tgt
    _tgt="$(heredoc_write_target "$line")"
    if [ -n "$_tgt" ] && heredoc_target_executed "$_tgt" "$i" "$end"; then
      continue
    fi

    i=$end                          # skip the body AND the terminator line
  done
  printf '%s' "$out"
}
