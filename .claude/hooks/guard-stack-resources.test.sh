#!/usr/bin/env bash
# Self-test for the stack-resource guard.
#
# Same discipline as its siblings: assert the DECISION parsed out of the JSON
# (these hooks deny with a permissionDecision and exit 0, so exit status carries
# no information), test the FALSE-POSITIVE direction at least as hard as the
# blocking one, and end with a mutation contract — a guard nobody proved can fail
# is indistinguishable from no guard (lessons §18).
set -u

HOOK="${HOOK:-$(cd "$(dirname "$0")" && pwd)/guard-stack-resources.sh}"
PASS=0; FAIL=0
STUB="$(mktemp -d)"
trap 'rm -rf "$STUB"' EXIT

# --- stubs: hermetic. No real docker, no real df. ---------------------------
# `df` is stubbed so the disk floor is testable in BOTH directions on any
# machine; `docker` is stubbed so the project check never touches a real daemon.
cat > "$STUB/df" <<'EOF'
#!/usr/bin/env bash
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
printf '/dev/stub %s %s %s 50%%  /\n' 100000000 1 "${DF_AVAIL_KB:-41943040}"
EOF
cat > "$STUB/docker" <<'EOF'
#!/usr/bin/env bash
case "$*" in
  "compose ls --format json") printf '%s' "${DOCKER_STUB_PROJECTS:-[]}" ;;
  *) exit 0 ;;
esac
EOF
chmod +x "$STUB/df" "$STUB/docker"
export PATH="$STUB:$PATH"

payload() { printf '{"tool_input":{"command":%s}}' "$(printf '%s' "$1" | jq -Rs .)"; }
decide() {
  local out
  out="$(printf '%s' "$(payload "$1")" | bash "$HOOK" 2>/dev/null)"
  case "$out" in *'"permissionDecision":"deny"'*) echo deny ;; *) echo allow ;; esac
}
run() { # run <name> <expected> <command>
  local got; got="$(decide "$3")"
  if [ "$got" = "$2" ]; then PASS=$((PASS+1));
  else FAIL=$((FAIL+1)); printf '  ✗ %s — expected %s, got %s\n' "$1" "$2" "$got"; fi
}
run_reason() { # run_reason <name> <substring> <command>
  local out reason
  out="$(printf '%s' "$(payload "$3")" | bash "$HOOK" 2>/dev/null)"
  reason="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason // ""' 2>/dev/null)"
  if printf '%s' "$reason" | grep -qF "$2"; then PASS=$((PASS+1));
  else FAIL=$((FAIL+1)); printf '  ✗ %s — reason lacked %s (got: %s)\n' "$1" "$2" "${reason:-<allow>}"; fi
}

ONE_GB=1048576
LOTS=$((60 * ONE_GB))
LOW=$((2 * ONE_GB))

echo "== stack-resource guard self-test =="

# --- Check A: the disk floor, both directions -------------------------------
DF_AVAIL_KB=$LOTS run "plenty of disk: compose up is fine" allow "docker compose up -d"
DF_AVAIL_KB=$LOW  run "below the floor: compose up is denied (FAILING-FIRST — this is the incident)" deny "docker compose up -d"
DF_AVAIL_KB=$LOW  run "below the floor: docker build is denied" deny "docker build -t x ."
DF_AVAIL_KB=$LOW  run "below the floor: compose build is denied" deny "docker compose build backend"
DF_AVAIL_KB=$LOW  run "below the floor: docker run is denied" deny "docker run --rm alpine true"
DF_AVAIL_KB=$LOW  run "below the floor: docker pull is denied" deny "docker pull postgres:16"
DF_AVAIL_KB=$LOW  run_reason "the deny explains the daemon-crash consequence, not just the number" \
  "crashed daemon" "docker compose up -d"
DF_AVAIL_KB=$LOW  run_reason "…and it does NOT recommend a rule-9 destructive prune" \
  "volume/system prune is NOT" "docker compose up -d"
DF_AVAIL_KB=$LOW DOCKER_DISK_FLOOR_GB=1 run "the floor is tunable downwards" allow "docker compose up -d"

# --- the false-positive direction: commands that FREE or only READ -----------
# These are the commands an agent runs while recovering from a full disk. If the
# guard blocks them it makes the incident WORSE, which is the failure mode that
# matters most here.
DF_AVAIL_KB=$LOW run "docker compose down is never blocked"  allow "docker compose down"
DF_AVAIL_KB=$LOW run "docker compose ps is never blocked"    allow "docker compose ps"
DF_AVAIL_KB=$LOW run "docker compose logs is never blocked"  allow "docker compose logs -f backend"
DF_AVAIL_KB=$LOW run "docker exec is never blocked"          allow "docker exec hirefolio-backend-1 env"
DF_AVAIL_KB=$LOW run "docker system df is never blocked"     allow "docker system df"
DF_AVAIL_KB=$LOW run "docker builder prune is never blocked" allow "docker builder prune -f"
DF_AVAIL_KB=$LOW run "docker image ls is never blocked"      allow "docker image ls"
DF_AVAIL_KB=$LOW run "a non-docker command is never blocked" allow "npm run build"
DF_AVAIL_KB=$LOW run "git commands are untouched"            allow "git status"

# Quoted prose is DATA (#204/#237) — the sibling hooks' hardest-won property.
DF_AVAIL_KB=$LOW run "the phrase quoted in a commit message is not a command" allow \
  "git commit -m 'never run docker compose up beside another stack'"
DF_AVAIL_KB=$LOW run "the phrase in a heredoc body is not a command" allow "cat > /tmp/n.md <<'MD'
Do not docker compose up a second project.
MD"
# The line above is protected by the argv[0] anchor as well as by the heredoc
# model, so it cannot tell the two apart. THIS one can: the body line starts with
# the command, so only strip_text_heredocs keeps it out of the parse.
DF_AVAIL_KB=$LOW run "a heredoc body LINE that *is* the command is still data" allow "cat > /tmp/n.md <<'MD'
docker compose up -d --build
MD"
DF_AVAIL_KB=$LOW run "…but a real up on the heredoc-opening line still gates" deny \
  "docker compose up -d --build && cat > /tmp/n.md <<'MD'
notes
MD"
DF_AVAIL_KB=$LOW run "an echo of the phrase is not a command" allow "echo 'next: docker compose up'"

# --- Check B: one compose project -------------------------------------------
BUSY='[{"Name":"hirefolio","Status":"running(8)"}]'
DF_AVAIL_KB=$LOTS DOCKER_STUB_PROJECTS="$BUSY" \
  run "a SECOND named project while one runs is denied (the parallel-agent incident)" deny \
  "docker compose -p hirefolio250 up -d"
DF_AVAIL_KB=$LOTS DOCKER_STUB_PROJECTS="$BUSY" \
  run_reason "…and the deny quotes the measured size of one stack" "15.35 GB" \
  "docker compose -p hirefolio250 up -d"
DF_AVAIL_KB=$LOTS DOCKER_STUB_PROJECTS="$BUSY" \
  run "REUSING the running project is exactly what we want, so it is allowed" allow \
  "docker compose -p hirefolio up -d"
DF_AVAIL_KB=$LOTS DOCKER_STUB_PROJECTS="$BUSY" \
  run "--project-name spelling is understood too" deny "docker compose --project-name other up -d"
DF_AVAIL_KB=$LOTS DOCKER_STUB_PROJECTS="$BUSY" \
  run "a COMPOSE_PROJECT_NAME prefix is understood too" deny "COMPOSE_PROJECT_NAME=other docker compose up -d"
DF_AVAIL_KB=$LOTS DOCKER_STUB_PROJECTS="$BUSY" DOCKER_STACK_ALLOW_PROJECTS=hirefolio250 \
  run "a deliberately allowed second project passes" allow "docker compose -p hirefolio250 up -d"
DF_AVAIL_KB=$LOTS DOCKER_STUB_PROJECTS='[]' \
  run "with nothing running, any project may start" allow "docker compose -p anything up -d"
# No -p at all: the effective name comes from the cwd, which this hook cannot
# know. It must stay silent rather than guess — a false deny here would block the
# ordinary `docker compose up` every agent runs.
DF_AVAIL_KB=$LOTS DOCKER_STUB_PROJECTS="$BUSY" \
  run "no explicit project name: the guard says nothing (documented limit)" allow "docker compose up -d"
# -f is value-taking; a file argument must not be read as the project name.
DF_AVAIL_KB=$LOTS DOCKER_STUB_PROJECTS="$BUSY" \
  run "a -f file argument is not mistaken for a project name" allow \
  "docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d"

# --- the bypass, typed the way the message advertises ------------------------
DF_AVAIL_KB=$LOW DOCKER_STACK_GUARD=0 run "DOCKER_STACK_GUARD=0 releases one command" allow "docker compose up -d"

echo "guard-stack-resources self-test: $PASS passed, $FAIL failed"

# --- Mutation contract -------------------------------------------------------
if [ "${1-}" = "--mutations" ]; then
  echo
  echo "== mutation contract =="
  MPASS=0; MFAIL=0; MBAD=0
  MDIR="$STUB/mut"; mkdir -p "$MDIR"
  cp "$(dirname "$HOOK")/hook-parse-lib.sh" "$MDIR/" || {
    echo "  ✗ HARNESS: cannot copy hook-parse-lib.sh"; exit 1; }
  WORK="$MDIR/guard-stack-resources.sh"

  mutate() { # mutate <die|survive> <name> <sed-expr>
    local expect="$1" name="$2" expr="$3" rc
    if [ "$expect" = "survive" ]; then cp "$HOOK" "$WORK"
    else
      sed "$expr" "$HOOK" > "$WORK"
      if cmp -s "$HOOK" "$WORK"; then
        echo "  ✗ INVALID: $name — produced NO diff, so it tests nothing"; MBAD=$((MBAD+1)); return
      fi
    fi
    bash -n "$WORK" 2>/dev/null || {
      echo "  ✗ INVALID: $name — mutant is not parseable"; MBAD=$((MBAD+1)); return; }
    HOOK="$WORK" bash "$0" >/dev/null 2>&1; rc=$?
    if [ "$expect" = "survive" ]; then
      if [ $rc -eq 0 ]; then echo "  ✓ control survived: $name"
      else echo "  ✗ HARNESS BROKEN: $name should survive but died"; MBAD=$((MBAD+1)); fi
      return
    fi
    if [ $rc -ne 0 ]; then MPASS=$((MPASS+1)); printf '  ✓ killed: %s\n' "$name"
    else MFAIL=$((MFAIL+1)); printf '  ✗ SURVIVED: %s\n' "$name"; fi
  }

  mutate survive "identity (byte-identical copy)" ""
  [ "$MBAD" -eq 0 ] || { echo "mutation contract: HARNESS INVALID"; exit 1; }

  mutate die "deny() emits allow instead of deny" 's/permissionDecision\\":\\"deny/permissionDecision\\":\\"allow/'
  mutate die "the disk floor never fires" 's/if \[ "\$AVAIL_GB" -lt "\$FLOOR_GB" \]; then/if false; then/'
  mutate die "the floor is read as 0" 's/FLOOR_GB="\${DOCKER_DISK_FLOOR_GB:-5}"/FLOOR_GB=0/'
  mutate die "the one-project check never fires" 's/  if \[ "\$hit" = "0" \]; then/  if false; then/'
  mutate die "explicit -p is ignored (every second stack passes)" 's/-p|--project-name) SEG_PROJECT="\${2:-}"/-p|--project-name) SEG_PROJECT=""/'
  mutate die "down, ps and logs are treated as resource-creating too" 's/    up|build|run|pull|create|start)/    up|build|run|pull|create|start|down|ps|logs|exec)/'
  mutate die "heredoc bodies are parsed as commands" 's/quote_split "\$(strip_text_heredocs "\$CMD")"/quote_split "$CMD"/'
  mutate die "the documented bypass stops working" 's/\[ "\${DOCKER_STACK_GUARD:-1}" = "0" \] \&\& allow/[ "${DOCKER_STACK_GUARD:-1}" = "9" ] \&\& allow/'

  echo "mutation contract: $MPASS killed, $MFAIL survived, $MBAD invalid"
  [ "$MFAIL" -eq 0 ] && [ "$MBAD" -eq 0 ] || exit 1
fi

[ "$FAIL" -eq 0 ]
