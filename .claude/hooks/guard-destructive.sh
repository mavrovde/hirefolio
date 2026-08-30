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

# A quoted argument that turns out to be shell code: put the newlines back, split
# it like a real script, and inspect every command in it. Returns 0 (and leaves
# REASON set) when something in there is blocked.
inspect_inner_script() {
  local body="$1" line inner
  case "$body" in
    *"$NL_SENTINEL"*) ;;
    *) return 1 ;;   # single-line: the caller's normal path already covers it
  esac
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
    if printf '%s' "$seg" | grep -Eq '^(bash|sh|zsh|dash) +-c '; then
      seg="$(printf '%s' "$seg" | sed -E "s/^(bash|sh|zsh|dash) +-c +//; s/^[\"']//")"; changed=1
      inspect_inner_script "$seg" && return 0
    elif printf '%s' "$seg" | grep -Eq '^eval '; then
      seg="$(printf '%s' "$seg" | sed -E "s/^eval +//; s/^[\"']//")"; changed=1
      inspect_inner_script "$seg" && return 0
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
  local s="$1" out="" i c q="" n=${#1}
  for (( i=0; i<n; i++ )); do
    c="${s:i:1}"
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

SEGMENTS="$(quote_split "$(strip_text_heredocs "$CMD")")"
OLDIFS="$IFS"; IFS=$'\n'
for seg in $SEGMENTS; do
  [ -n "$REASON" ] && break
  inspect_segment "$seg"
done
IFS="$OLDIFS"

[ -n "$REASON" ] && deny "$REASON"
allow
