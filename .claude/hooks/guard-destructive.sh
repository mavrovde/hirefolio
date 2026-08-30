#!/usr/bin/env bash
# Guardrail against irreversible LOCAL/infra destruction (issue #116).
#
# A PreToolUse `Bash` hook: it inspects the command JSON on stdin and BLOCKS
# (permissionDecision: "deny") a small, high-blast-radius set of destructive
# commands that would wipe stateful local resources the user never explicitly
# authorized destroying — Docker volumes, whole non-`test_*` databases, or data
# directories. Defense-in-depth BEYOND the generic permission classifier, which
# only blocked the #91 incident (`docker volume rm mavrovde_open-webui_data`) by
# luck.
#
# COMMAND-POSITION AWARE: it matches only when a destructive command is actually
# being *invoked* — not when the same text merely appears as an argument (a
# `git commit -m "...docker volume rm..."` message, a `grep`/`echo` of the
# pattern, docs). It splits the command on shell separators and inspects the
# FIRST token of each segment; segments whose command is a text/VCS tool
# (git/grep/echo/cat/sed/awk/…) are skipped. It also transparently unwraps common
# indirection — `sudo`/`env`/`nohup`/`time`, `xargs [opts]`, and `bash -c` /
# `sh -c` / `eval "…"` — so `… | xargs docker volume rm` (the "remove ALL volumes"
# idiom) and `bash -c "docker volume rm x"` are still caught. It never interferes
# with normal work (build, test, `verify_all.sh`, `manage.sh`, `test_*` teardown).
#
# A backup is NOT consent: to run one of these deliberately, either export
# GUARD_DESTRUCTIVE=0 for an authorized session, or prefix that ONE command's
# segment with the bypass token, e.g.  GUARD_DESTRUCTIVE=0 docker volume rm <name>
# (the bypass is honored only as a LEADING env-assignment of the segment being
# guarded — a stray `GUARD_DESTRUCTIVE=0` elsewhere in the line does not disarm it).
set -uo pipefail
# Segments are iterated via unquoted command substitution (word-splitting on
# newlines is exactly what we want there). Without `-f`, a segment containing a
# glob character would additionally be rewritten by whatever files happen to sit
# in the working directory — so what the guard inspects could differ from what
# was typed. Disable pathname expansion for the whole script.
set -f

# Session master switch (inherited from the hook's environment / settings env).
: "${GUARD_DESTRUCTIVE:=1}"

allow() {
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
  exit 0
}
deny() {
  # $1 = reason (plain text, no double quotes — it is embedded in JSON)
  printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"$1\"}}"
  exit 0
}

[ "$GUARD_DESTRUCTIVE" = "1" ] || allow

INPUT="$(cat)"
CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -z "$CMD" ] && CMD="$INPUT"

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

REASON=""

# Stand-in for a newline that appeared INSIDE quotes. Chosen as a control
# character so it can never occur in a real command and is not whitespace, which
# keeps it intact through the space-collapsing normaliser below.
NL_SENTINEL=$'\x01'

# Nesting depth of shell-wrapper unwrapping (see inspect_inner_script).
INNER_DEPTH=0

# A quoted argument that turns out to be shell code: put the newlines back, split
# it like a real script, and inspect every command in it. Returns 0 (and leaves
# REASON set) when something in there is blocked.
inspect_inner_script() {
  local body="$1" line inner
  # Recursion guard: wrappers can nest (`bash -c "bash -c '…'"`). The depth is
  # bounded so a pathological input cannot spin here; hitting the bound is
  # treated as "cannot analyse", and the caller's normal path still applies.
  # Depth bound. It must fail CLOSED: returning "nothing found" at the bound
  # would mean 8 stacked wrappers deny and 9 allow, i.e. the bypass is simply
  # "nest one level deeper". At the bound we stop analysing and say so.
  if [ "$INNER_DEPTH" -ge 8 ]; then
    REASON="BLOCKED: command nests shell wrappers more than 8 deep, which this guard will not attempt to analyse. Simplify the command, or prefix it with GUARD_DESTRUCTIVE=0 if it is authorized."
    return 0
  fi
  INNER_DEPTH=$((INNER_DEPTH + 1))

  # Restore any quoted newlines, then split on them. A body with NO newline is
  # still processed: `bash -c "echo hi; <destroy>"` packs its commands with a
  # semicolon, and because that separator sat inside the wrapper's quotes the
  # outer quote_split protected it — leaving one segment whose benign first
  # token hid the rest (#210).
  body="${body//$NL_SENTINEL/$'\n'}"

  # Split on the restored NEWLINES FIRST, then apply quote_split within each
  # line. Order matters: re-running quote_split over the whole body would see
  # those newlines still sitting inside the wrapper's quotes and protect them all
  # over again, collapsing the script back into one segment — which is how
  # `ssh -p 2222 host "echo hi ↵ <destroy>"` slipped through. Splitting per line
  # also means an unbalanced quote on one line cannot shield the next.
  local OLD="$IFS"
  while IFS= read -r line; do
    [ -n "$REASON" ] && break
    IFS=$'\n'
    for inner in $(quote_split "$line"); do
      [ -n "$REASON" ] && break
      inspect_segment "$inner"
    done
    IFS="$OLD"
  done <<< "$body"
  IFS="$OLD"
  INNER_DEPTH=$((INNER_DEPTH - 1))
  [ -n "$REASON" ]
}

# Inspect one command segment (already separator-split). Sets REASON on a hit.
inspect_segment() {
  local seg="$1"
  seg="$(printf '%s' "$seg" | tr '\n\t' '  ' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+/ /g')"

  # Peel leading env-assignments; a leading GUARD_DESTRUCTIVE=0 authorizes THIS
  # segment specifically (deliberate, scoped bypass).
  while printf '%s' "$seg" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*='; do
    printf '%s' "$seg" | grep -Eq '^GUARD_DESTRUCTIVE=0([ ]|$)' && return 0
    seg="$(printf '%s' "$seg" | sed -E 's/^[A-Za-z_][A-Za-z0-9_]*=[^ ]* ?//')"
  done

  # Transparently unwrap indirection so wrapped invocations are still inspected.
  # Loop because wrappers stack (e.g. `sudo env FOO=bar xargs docker volume rm`).
  local changed=1 guard=0
  while [ "$changed" = "1" ] && [ "$guard" -lt 8 ]; do
    changed=0; guard=$((guard + 1))
    # sudo / command / nohup / time / exec / env (simple prefixes)
    if printf '%s' "$seg" | grep -Eq '^(sudo|command|nohup|time|exec|env) '; then
      seg="$(printf '%s' "$seg" | sed -E 's/^(sudo|command|nohup|time|exec|env) +//')"; changed=1
    fi
    # more env-assignments after a wrapper
    while printf '%s' "$seg" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*='; do
      printf '%s' "$seg" | grep -Eq '^GUARD_DESTRUCTIVE=0([ ]|$)' && return 0
      seg="$(printf '%s' "$seg" | sed -E 's/^[A-Za-z_][A-Za-z0-9_]*=[^ ]* ?//')"; changed=1
    done
    # xargs [options...] <cmd> — drop `xargs` and its option/replacement tokens.
    if printf '%s' "$seg" | grep -Eq '^xargs( |$)'; then
      seg="$(printf '%s' "$seg" | sed -E 's/^xargs +//')"
      # strip leading xargs options: -0, -n1, -P4, -I{}, -I '{}', --max-args=1, {}
      while printf '%s' "$seg" | grep -Eq '^(-[^ ]+|\{\}|[A-Za-z]=)( |$)'; do
        seg="$(printf '%s' "$seg" | sed -E 's/^(-[^ ]+|\{\}|[A-Za-z]=) +//; s/^(-[^ ]+|\{\})$//')"
      done
      changed=1
    fi
    # bash -c "…" / sh -c '…' / zsh -c … / eval … / ssh host "…" — the quoted
    # argument is a SCRIPT, so inspect the command(s) inside it.
    #
    # Two passes are needed, and BOTH matter. `inspect_inner_script` re-splits the
    # body so packed separators are seen (#210) — but `quote_split` also treats
    # `(`, `)` and backtick as separators, so a command substitution in the middle
    # of an invocation FRAGMENTS it, and the multi-condition rules (compose +
    # `down` + `-v`; `rm` + recursive + data path) never see all their conditions
    # in one piece. Falling through afterwards re-inspects the FLATTENED body as a
    # single segment, which is what catches those. Returning early here made the
    # guard strictly weaker than before on six protected paths.
    if printf '%s' "$seg" | grep -Eq '^(bash|sh|zsh|dash) +-c '; then
      seg="$(printf '%s' "$seg" | sed -E "s/^(bash|sh|zsh|dash) +-c +//; s/^[\"']//")"
      inspect_inner_script "$seg" && return 0
      changed=1
    elif printf '%s' "$seg" | grep -Eq '^eval '; then
      seg="$(printf '%s' "$seg" | sed -E "s/^eval +//; s/^[\"']//")"
      inspect_inner_script "$seg" && return 0
      changed=1
    elif printf '%s' "$seg" | grep -Eq '^ssh '; then
      # `ssh host "…"` runs its argument on the remote shell. Same reasoning, and
      # the blast radius there is someone else's machine.
      #
      # Inspect the WHOLE remainder first, before any attempt to parse options
      # and host. ssh's option grammar is a swamp (`-p 2222`, `-p2222`,
      # `-o Port=22`, `-i key`, `user@host`), and a parser that guesses wrong
      # eats the flag's value as the host and the real host as the command —
      # which silently skips inspection. Inspecting first makes the body's
      # protection independent of getting that grammar right.
      local rest="${seg#ssh }"
      inspect_inner_script "$rest" && return 0

      # Then best-effort strip options (consuming the values of value-taking
      # flags) and the host, so a SINGLE-LINE `ssh host <destroy>` is inspected
      # as a command rather than as an argument.
      while [ "${rest:0:1}" = "-" ]; do
        local flag="${rest%% *}"
        [ "$flag" = "$rest" ] && break
        rest="${rest#* }"
        case "$flag" in
          -[bcDEeFIiJLlmOopQRSWw]) rest="${rest#* }" ;;  # flag took a separate value
        esac
      done
      seg="$(printf '%s' "$rest" | sed -E "s/^[^ ]+ +//; s/^[\"']//")"
      changed=1
    fi
  done

  # `find … -exec <cmd> …` — inspect the command that follows -exec/-execdir.
  if printf '%s' "$seg" | grep -Eq ' -execdir? '; then
    local post
    post="$(printf '%s' "$seg" | sed -E 's/^.* -execdir? +//')"
    [ -n "$post" ] && [ "$post" != "$seg" ] && inspect_segment "$post"
    [ -n "$REASON" ] && return 0
  fi

  # Anything still carrying sentinels is NOT shell code (the branches above would
  # have recursed), so those newlines really were data: flatten them to spaces so
  # the segment reads as the one quoted argument it is.
  seg="${seg//$NL_SENTINEL/ }"
  seg="$(printf '%s' "$seg" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+/ /g')"

  local first="${seg%% *}"
  [ -z "$first" ] && return 0
  is_text_tool "$first" && return 0

  # 1. Docker volume destruction: `docker volume rm|prune`
  if printf '%s' "$seg" | grep -Eq '^docker +volume +(rm|prune)\b'; then
    REASON="BLOCKED: 'docker volume rm/prune' destroys named Docker volumes (DB / open-webui / model data). Irreversible and not authorized. If the user named this volume to delete, prefix that command with GUARD_DESTRUCTIVE=0."
    return 0
  fi
  # 2. Compose teardown that also removes volumes: `docker compose ... down -v`
  if printf '%s' "$seg" | grep -Eq '^docker(-compose| +compose)\b' \
     && printf '%s' "$seg" | grep -Eq '\bdown\b' \
     && printf '%s' "$seg" | grep -Eq '(-v\b|--volumes\b)'; then
    REASON="BLOCKED: 'docker compose down -v/--volumes' deletes the stack's named volumes (Postgres, ollama, open-webui). Use 'down' without -v to stop containers while keeping data. Prefix GUARD_DESTRUCTIVE=0 only if wiping these volumes was authorized."
    return 0
  fi
  # 3. System / image prune
  if printf '%s' "$seg" | grep -Eq '^docker +system +prune\b'; then
    REASON="BLOCKED: 'docker system prune' mass-deletes stopped containers / networks / build cache (and volumes with --volumes). Not authorized as an autonomous action. Prefix GUARD_DESTRUCTIVE=0 if explicitly asked."
    return 0
  fi
  if printf '%s' "$seg" | grep -Eq '^docker +image +prune\b' \
     && printf '%s' "$seg" | grep -Eq '(-a\b|--all\b)'; then
    REASON="BLOCKED: 'docker image prune -a' removes ALL images not used by a running container (slow to recover). Prefix GUARD_DESTRUCTIVE=0 if explicitly authorized."
    return 0
  fi
  # 4. Dropping a non-`test_*` database.
  if printf '%s' "$seg" | grep -Eq '^dropdb\b'; then
    if ! printf '%s' "$seg" | grep -Eq '(^|[ ])test_[A-Za-z0-9_]+([ ]|$)'; then
      REASON="BLOCKED: 'dropdb' on a non-test database is irreversible data loss. Only 'test_*' databases may be dropped autonomously. Prefix GUARD_DESTRUCTIVE=0 if the user named this DB to drop."
      return 0
    fi
  fi
  # 4b. SQL DROP DATABASE/SCHEMA via a DB client (psql/docker exec ... psql, etc).
  if printf '%s' "$seg" | grep -Eiq 'DROP +(DATABASE|SCHEMA)\b'; then
    if ! printf '%s' "$seg" | grep -Eiq 'DROP +(DATABASE|SCHEMA)( +IF +EXISTS)? +"?test_[A-Za-z0-9_]+'; then
      REASON="BLOCKED: 'DROP DATABASE/SCHEMA' on a non-test target is irreversible. Only 'test_*' targets are allowed autonomously. Prefix GUARD_DESTRUCTIVE=0 if authorized."
      return 0
    fi
  fi
  # 5. RECURSIVE rm targeting a persistent data / volume / mount path.
  #    `-f` is deliberately NOT required (#188): `rm -R ./data` destroys the
  #    directory just as irreversibly — the force flag only suppresses prompts
  #    for write-protected files, it is not what makes the delete dangerous.
  #    Flag-order and spelling agnostic: short clusters (-rf, -fr, -Rf, -R, -r),
  #    separated flags in any order, and the long form --recursive.
  if printf '%s' "$seg" | grep -Eq '^rm ' \
     && printf '%s' "$seg" | grep -Eq '(^|[ ])(-[A-Za-z]*[rR][A-Za-z]*|--recursive)([ ]|$)'; then
    # Boundaries accept a surrounding quote too: `rm -R "./data"` is the same
    # delete as `rm -R ./data`, but a trailing `"` used to defeat the `([/ ]|$)`
    # terminator and slip through (found reviewing #188).
    if printf '%s' "$seg" | grep -Eiq '(^|[ =/"'"'"'])(data|pgdata|postgres[-_]?data|db[-_]?data|volumes?|ollama|open-webui|\.chrome-profile|linkedin_cookies)([/ "'"'"']|$)'; then
      REASON="BLOCKED: recursive 'rm' targeting a persistent data/volume path (data/pgdata/volumes/ollama/open-webui/.chrome-profile/…). Irreversible and unauthorized. Prefix GUARD_DESTRUCTIVE=0 only for a path the user explicitly told you to delete."
      return 0
    fi
  fi
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
      if [ -n "$q" ] && [ "$nx" = $'\n' ]; then out+="$NL_SENTINEL"; else out+="$c$nx"; fi
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
      [ "$c" = "$q" ] && q=""
      continue
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
      [ "$c" = "$q" ] && q=""
      continue
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
  local input="$1" out="" line delim i j n end
  local -a lines=()
  while IFS= read -r line; do lines+=("$line"); done <<< "$input"
  n=${#lines[@]}
  for (( i=0; i<n; i++ )); do
    line="${lines[i]}"
    out+="$line"$'\n'

    delim="$(heredoc_delim "$line")"
    [ -z "$delim" ] && continue
    line_is_all_text_tools "$line" || continue

    end=-1
    for (( j=i+1; j<n; j++ )); do
      if [ "$(printf '%s' "${lines[j]}" | sed -E 's/^[[:space:]]+//')" = "$delim" ]; then
        end=$j; break
      fi
    done
    [ "$end" -lt 0 ] && continue   # no terminator: strip nothing

    i=$end                          # skip the body AND the terminator line
  done
  printf '%s' "$out"
}

# Is any segment a BARE shell — i.e. a shell reading its script from stdin?
# `… | bash`, `… | sh -s`, `… | sudo bash`. That construct means "execute the
# text that reaches me", so quoted text earlier in the pipeline is CODE, however
# innocent its producing command looks (#210).
pipes_into_shell() {
  local seg first via_xargs
  local OLD="$IFS"; IFS=$'\n'
  for seg in $1; do
    # Peel wrappers, including ones that take their own options (`sudo -E`,
    # `xargs -0`), then an absolute path — `/bin/bash` is as much a shell as
    # `bash`. Matching two exact spellings made this an allowlist of the first
    # two forms that came to mind; every other spelling executed unguarded.
    seg="$(printf '%s' "$seg" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+/ /g')"
    via_xargs=0
    while printf '%s' "$seg" | grep -Eq '^(sudo|env|command|exec|nohup|time|xargs)( |$)'; do
      printf '%s' "$seg" | grep -Eq '^xargs( |$)' && via_xargs=1
      seg="$(printf '%s' "$seg" | sed -E 's/^(sudo|env|command|exec|nohup|time|xargs) *//')"
      while printf '%s' "$seg" | grep -Eq '^-'; do
        seg="$(printf '%s' "$seg" | sed -E 's/^-[^ ]* *//')"
      done
    done
    seg="$(printf '%s' "$seg" | sed -E 's#^/[^ ]*/##')"
    first="${seg%% *}"
    case "$first" in
      bash|sh|zsh|dash)
        # Anything that is NOT `-c` reads its script from somewhere else — stdin
        # (bare, or `-s`, or `-`), a here-string, a process substitution — and in
        # every one of those the text arriving from the pipeline is code.
        # `-c` normally means the script is the argument, which inspect_segment
        # already unwraps — EXCEPT behind xargs, which appends the piped text as
        # that very argument. There the payload is still code arriving by pipe.
        if [ "$via_xargs" = 1 ]; then IFS="$OLD"; return 0; fi
        case "$seg" in
          *" -c "*|*" -c") ;;                       # script is the argument; handled elsewhere
          *) IFS="$OLD"; return 0 ;;
        esac
        ;;
    esac
  done
  IFS="$OLD"; return 1
}

# The contents of each quoted region in a segment, one per line.
quoted_payloads() {
  local s="$1" cur="" i c q="" n=${#1}
  for (( i=0; i<n; i++ )); do
    c="${s:i:1}"
    if [ "$c" = '\' ] && [ "$q" != "'" ] && [ $((i + 1)) -lt "$n" ]; then
      [ -n "$q" ] && cur+="${s:i+1:1}"
      i=$((i + 1)); continue
    fi
    if [ -n "$q" ]; then
      if [ "$c" = "$q" ]; then q=""; printf '%s\n' "$cur"; cur=""; else cur+="$c"; fi
      continue
    fi
    case "$c" in \'|\") q="$c" ;; esac
  done
  [ -n "$q" ] && [ -n "$cur" ] && printf '%s\n' "$cur"
}

SEGMENTS="$(quote_split "$(strip_text_heredocs "$CMD")")"

# When the command feeds a shell from stdin, re-read every quoted argument in it
# as a script before the normal pass. Without this, `printf "%s" "<destroy>" |
# bash` is two segments — one led by a text tool, one that is just `bash` — and
# neither looks destructive on its own.
if pipes_into_shell "$SEGMENTS"; then
  OLDIFS="$IFS"; IFS=$'\n'
  for seg in $SEGMENTS; do
    [ -n "$REASON" ] && break
    for payload in $(quoted_payloads "$seg"); do
      [ -n "$REASON" ] && break
      inspect_inner_script "$payload"
    done
  done
  IFS="$OLDIFS"
fi

OLDIFS="$IFS"; IFS=$'\n'
for seg in $SEGMENTS; do
  [ -n "$REASON" ] && break
  inspect_segment "$seg"
done
IFS="$OLDIFS"

[ -n "$REASON" ] && deny "$REASON"
allow
