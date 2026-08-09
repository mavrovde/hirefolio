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
# (git/grep/echo/cat/sed/awk/…) are skipped. So it never interferes with normal
# work (build, test, `verify_all.sh`, `manage.sh`, pytest's `test_*` teardown).
#
# A backup is NOT consent: to run one of these deliberately, either export
# GUARD_DESTRUCTIVE=0 for an authorized session, or prefix the single command
# with the bypass token, e.g.  GUARD_DESTRUCTIVE=0 docker volume rm <name>
set -uo pipefail

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

# Inline per-command bypass: an explicit `GUARD_DESTRUCTIVE=0` in the command
# is a deliberate, authorized override.
printf '%s' "$CMD" | grep -Eq '(^|[^A-Za-z_])GUARD_DESTRUCTIVE=0([^0-9]|$)' && allow

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

# Inspect one command segment (already separator-split). Sets REASON on a hit.
inspect_segment() {
  local seg="$1"
  # Collapse whitespace; strip leading env-assignments and an optional `sudo`.
  seg="$(printf '%s' "$seg" | tr '\n\t' '  ' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+/ /g')"
  while printf '%s' "$seg" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*='; do
    seg="$(printf '%s' "$seg" | sed -E 's/^[A-Za-z_][A-Za-z0-9_]*=[^ ]* ?//')"
  done
  seg="$(printf '%s' "$seg" | sed -E 's/^(sudo|command|env|nohup|time|exec) +//g')"
  # Strip env-assignments again (e.g. `env FOO=bar cmd` / `sudo FOO=bar cmd`).
  while printf '%s' "$seg" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*='; do
    seg="$(printf '%s' "$seg" | sed -E 's/^[A-Za-z_][A-Za-z0-9_]*=[^ ]* ?//')"
  done

  local first="${seg%% *}"
  [ -z "$first" ] && return 0
  is_text_tool "$first" && return 0

  # 1. Docker volume destruction: `docker volume rm|prune`
  if printf '%s' "$seg" | grep -Eq '^docker +volume +(rm|prune)\b'; then
    REASON="BLOCKED: 'docker volume rm/prune' destroys named Docker volumes (DB / open-webui / model data). Irreversible and not authorized. If the user named this volume to delete, prefix the command with GUARD_DESTRUCTIVE=0."
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
  #     Caught even though it's a quoted arg, because the segment's command is a
  #     DB tool (not a text tool) — e.g. `psql -c "DROP DATABASE mavrov"`.
  if printf '%s' "$seg" | grep -Eiq 'DROP +(DATABASE|SCHEMA)\b'; then
    if ! printf '%s' "$seg" | grep -Eiq 'DROP +(DATABASE|SCHEMA)( +IF +EXISTS)? +"?test_[A-Za-z0-9_]+'; then
      REASON="BLOCKED: 'DROP DATABASE/SCHEMA' on a non-test target is irreversible. Only 'test_*' targets are allowed autonomously. Prefix GUARD_DESTRUCTIVE=0 if authorized."
      return 0
    fi
  fi
  # 5. `rm -rf` targeting a persistent data / volume / mount path.
  if printf '%s' "$seg" | grep -Eq '^rm +(-[A-Za-z]*r[A-Za-z]*f|-[A-Za-z]*f[A-Za-z]*r|-r +-f|-f +-r)\b'; then
    if printf '%s' "$seg" | grep -Eiq '(^|[ =/])(data|pgdata|postgres[-_]?data|db[-_]?data|volumes?|ollama|open-webui|\.chrome-profile|linkedin_cookies)([/ ]|$)'; then
      REASON="BLOCKED: 'rm -rf' targeting a persistent data/volume path (data/pgdata/volumes/ollama/open-webui/.chrome-profile/…). Irreversible and unauthorized. Prefix GUARD_DESTRUCTIVE=0 only for a path the user explicitly told you to delete."
      return 0
    fi
  fi
  return 0
}

# Split the command into segments on shell separators (; && || | newline & and
# subshell/substitution boundaries), then inspect each. Uses a literal newline
# delimiter so quoted text can't smuggle a destructive invocation past us.
SEGMENTS="$(printf '%s' "$CMD" | sed -E 's/\$\(|`|\)|\(/\n/g; s/(&&|\|\||;|\||&)/\n/g')"
OLDIFS="$IFS"; IFS=$'\n'
for seg in $SEGMENTS; do
  [ -n "$REASON" ] && break
  inspect_segment "$seg"
done
IFS="$OLDIFS"

[ -n "$REASON" ] && deny "$REASON"
allow
