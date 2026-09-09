#!/usr/bin/env bash
# Stack-resource guard (v1.14.0 retrospective) — PreToolUse Bash.
#
# WHY THIS EXISTS — the single largest wall-clock loss of the v1.14.0 cycle, and
# the only one that took the machine down rather than a PR:
#   Parallel agents each composed their OWN Docker stack (`hirefolio-*`,
#   `hirefolio250-*`, `mavrovde-*` running simultaneously). The disk reached zero,
#   the Docker daemon crashed, and the harness could no longer even write command
#   output — so the failure was invisible from inside the session that caused it.
#   Recovery took roughly two hours across two sessions, and #322's round-1 fix
#   report had to ship with its backend gates explicitly declared UNMEASURED.
#
# The numbers that make "one stack" a resource fact rather than a preference,
# measured on this project on 2026-09-09 (`docker system df`):
#   images 15.35 GB · build cache 3.09 GB · volumes 6.97 GB.
# A second stack does not fit beside the first on a laptop that had 7.7 GB free.
# The repo's own E2E and integration tiers are deliberately built to REUSE the
# `hirefolio` project for this reason (`run_integration_tests.sh` layers an
# overlay onto the dev compose; it does not start a second project).
#
# WHAT IT DOES — two checks, only on commands that CREATE stack resources
# (`docker compose up`, `docker compose build`, `docker build`, `docker run`,
# `docker pull`); everything else, including `down`, `ps`, `logs` and `exec`, is
# untouched:
#   A. FREE DISK FLOOR. Below the floor, creating more is how the daemon dies.
#   B. ONE PROJECT. Starting a compose project while a DIFFERENT one is running
#      is denied by name.
#
# It is deliberately narrow. It is not a quota system and it cannot see a build
# that arrives through a script file — that is the same command-text boundary the
# sibling hooks document, and pretending otherwise would be the false comfort
# `pre-merge-gate.sh`'s header warns about. Name the case that matters HERE rather
# than leaving it generic (#329 review, nit 10): **`./manage.sh start` is this
# repo's own primary bring-up command and is INVISIBLE to this guard**, because
# the `docker compose up` inside it is file contents, not command text. So is
# `./verify_all.sh` and `./run_integration_tests.sh`. Check free disk before
# running those by hand; the guard covers the direct `docker …` form an agent
# types, not the wrappers.
#
# Bypass ONE authorized command with:  DOCKER_STACK_GUARD=0 docker compose up …
# Tune with: DOCKER_DISK_FLOOR_GB (default 5), DOCKER_STACK_ALLOW_PROJECTS
# (space- or comma-separated extra project names that may run alongside).
set -u

allow() { exit 0; }
deny() {
  printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"STACK GUARD: $1 | Bypass one authorized command with DOCKER_STACK_GUARD=0\"}}"
  exit 0
}

[ "${DOCKER_STACK_GUARD:-1}" = "0" ] && allow

INPUT="$(cat)"
CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -z "$CMD" ] && allow

# Cheap reject before any parsing: the overwhelming majority of commands are not
# docker at all, and this hook runs on EVERY Bash call.
case "$CMD" in *docker*) ;; *) allow ;; esac

# The ONE parsing model (#237) — quoted prose is data, not commands.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hook-parse-lib.sh"

# Above this the analysis cannot be trusted to finish inside the hook timeout.
# Allow rather than deny: unlike the merge gate this hook guards a RECOVERABLE
# resource, and a false deny on a giant command would block ordinary work.
[ "${#CMD}" -gt 24576 ] && allow

FLOOR_GB="${DOCKER_DISK_FLOOR_GB:-5}"

creates_resources() { # <segment> -> 0 if this segment creates docker resources
  local seg="$1"
  case "$seg" in *docker*) ;; *) return 1 ;; esac
  # THE DOCUMENTED BYPASS LIVES HERE, not in the hook's own environment. A caller
  # types `DOCKER_STACK_GUARD=0 docker compose up -d`, so the token is part of the
  # COMMAND TEXT; the env read at the top of this file only fires when the hook
  # PROCESS inherited the variable, which nothing in this harness does — shell
  # state does not persist between Bash tool calls. Shipping without this made the
  # printed remedy a deny loop with no exit, which is the "makes the incident
  # worse" failure mode this hook exists to prevent (#329 review round 1). Same
  # regex and same per-segment position as guard-destructive.sh:242 and
  # pre-merge-gate.sh:134 — one model, three hooks (#237).
  if printf '%s' "$seg" | grep -Eq '^([A-Za-z_][A-Za-z0-9_]*=[^ ]* )*DOCKER_STACK_GUARD=0( |$)'; then
    return 1   # authorized: this segment is not gated
  fi
  argv_split "$seg"
  [ "${#ARGV_SPLIT_RESULT[@]}" -eq 0 ] && return 1
  set -- "${ARGV_SPLIT_RESULT[@]}"
  # A `VAR=value docker …` prefix is common (COMPOSE_PROJECT_NAME=x docker …).
  while [ $# -gt 0 ]; do
    case "$1" in
      COMPOSE_PROJECT_NAME=*) SEG_PROJECT="${1#COMPOSE_PROJECT_NAME=}"; shift ;;
      *=*) shift ;;
      *) break ;;
    esac
  done
  case "${1:-}" in docker|docker-compose) ;; *) return 1 ;; esac
  local is_compose=0
  [ "${1:-}" = "docker-compose" ] && is_compose=1
  shift
  # Walk docker's own flags, and compose's, keeping any project name.
  while [ $# -gt 0 ]; do
    case "$1" in
      compose) is_compose=1; shift ;;
      -p|--project-name) SEG_PROJECT="${2:-}"; shift 2 || return 1 ;;
      -p=*|--project-name=*) SEG_PROJECT="${1#*=}"; shift ;;
      -f|--file|--project-directory|--env-file|-H|--host|--context|--profile) shift 2 || return 1 ;;
      -*) shift ;;
      *) break ;;
    esac
  done
  case "${1:-}" in
    # `start` is deliberately NOT here (#329 review, minor 7): it starts EXISTING
    # containers and writes no image, layer or build cache, and it is a plausible
    # step AFTER reclaiming space. `create` stays — it writes a container's
    # read-write layer, so it does consume the resource this floor protects.
    up|build|run|pull|create) [ "$is_compose" = "1" ] && return 0 ;;
  esac
  case "${1:-}" in
    build|run|pull) [ "$is_compose" = "0" ] && return 0 ;;
  esac
  return 1
}

FOUND=0
SEG_PROJECT=""
PROJECTS=()
OLD_IFS="$IFS"
IFS=$'\n'
for seg in $(quote_split "$(strip_text_heredocs "$CMD")"); do
  SEG_PROJECT=""
  if creates_resources "$seg"; then
    FOUND=1
    [ -n "$SEG_PROJECT" ] && PROJECTS+=("$SEG_PROJECT")
  fi
done
IFS="$OLD_IFS"

[ "$FOUND" = "0" ] && allow

# --- Check A: free disk floor ------------------------------------------------
# `df -Pk` is the POSIX form and behaves the same on macOS (BSD) and Linux —
# `df -h` output is NOT parseable across both (env-gotchas).
#
# WHICH filesystem (#329 review, minor 6): the cwd is the right probe on macOS,
# where Docker Desktop's disk image lives under the user's home, but on Linux the
# data root is usually /var/lib/docker on a SEPARATE volume — so the cwd alone
# would measure a filesystem the build never touches. Both are probed and the
# SMALLER wins. Deliberately NOT `docker info -f '{{.DockerRootDir}}'`: this hook
# fires exactly when the daemon may be wedged, and a hanging daemon call would
# outlive the hook timeout — and a timed-out PreToolUse hook does not deny, it
# ALLOWS (#219). Override the path with DOCKER_DATA_ROOT.
avail_kb_of() { df -Pk "$1" 2>/dev/null | awk 'NR==2 {print $4}'; }
AVAIL_KB="$(avail_kb_of .)"
DATA_ROOT="${DOCKER_DATA_ROOT:-/var/lib/docker}"
if [ -d "$DATA_ROOT" ]; then
  ROOT_KB="$(avail_kb_of "$DATA_ROOT")"
  if [ -n "${ROOT_KB:-}" ] && [ "$ROOT_KB" -eq "$ROOT_KB" ] 2>/dev/null; then
    if [ -z "${AVAIL_KB:-}" ] || [ "$ROOT_KB" -lt "$AVAIL_KB" ]; then AVAIL_KB="$ROOT_KB"; fi
  fi
fi
if [ -n "${AVAIL_KB:-}" ] && [ "$AVAIL_KB" -eq "$AVAIL_KB" ] 2>/dev/null; then
  AVAIL_GB=$((AVAIL_KB / 1024 / 1024))
  if [ "$AVAIL_GB" -lt "$FLOOR_GB" ]; then
    deny "only ${AVAIL_GB} GB free (floor ${FLOOR_GB} GB) — creating Docker resources here is how the daemon died in the v1.14.0 cycle, and a crashed daemon takes the harness's command output with it. Reclaim space first (docker builder prune is safe; volume/system prune is NOT, rule 9), or raise DOCKER_DISK_FLOOR_GB deliberately"
  fi
fi

# --- Check B: one compose project --------------------------------------------
# Only when a project name is EXPLICIT in the command. Without `-p` the effective
# name comes from the working directory, which this hook cannot know (the command
# may `cd` first, and worktrees are exactly how the collision happened) — so it
# says nothing rather than guessing, and check A still applies. Stated as a limit,
# not implied.
[ "${#PROJECTS[@]}" -eq 0 ] && allow
command -v docker >/dev/null 2>&1 || allow

RUNNING="$(docker compose ls --format json 2>/dev/null | jq -r '.[]?.Name // empty' 2>/dev/null | sort -u)"
[ -z "$RUNNING" ] && allow

ALLOWED="$(printf '%s %s' "$RUNNING" "${DOCKER_STACK_ALLOW_PROJECTS:-}" | tr ',' ' ')"
for p in "${PROJECTS[@]}"; do
  [ -z "$p" ] && continue
  hit=0
  for a in $ALLOWED; do [ "$p" = "$a" ] && hit=1; done
  if [ "$hit" = "0" ]; then
    deny "compose project '$p' would run alongside already-running project(s) '$(printf '%s' "$RUNNING" | tr '\n' ' ')'. One stack of this project is 15.35 GB of images + 3.09 GB of build cache + 6.97 GB of volumes (measured 2026-09-09) — three concurrent stacks filled the disk and crashed the daemon in the v1.14.0 cycle. Reuse the running project, stop it first, or name it in DOCKER_STACK_ALLOW_PROJECTS if a second stack is genuinely intended"
  fi
done

exit 0
