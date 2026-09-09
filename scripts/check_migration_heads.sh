#!/usr/bin/env bash
# Alembic head contract (v1.14.0 retrospective) — the migration chain must have
# EXACTLY ONE head, in the working tree AND in the result of merging it with the
# branch it targets.
#
# WHY THIS EXISTS — measured, not hypothetical (#323 / #325, 2026-09-09):
#   `tailored0010` (#323) and `engage0010` (#325) were written in parallel and
#   BOTH declared `down_revision = "trans0009"`. Each branch was single-head in
#   isolation, so every gate the two PRs ran was green:
#       * the PR-level `Backend Migrations (drift guard)` job passed on both,
#       * `alembic heads` printed one head on both,
#       * 1138 / 1134 backend tests passed on both.
#   The fork existed only in the MERGED result. #323 merged at 10:35Z; #325's
#   last CI run had been computed against the pre-#323 base and GitHub does not
#   re-run a PR's checks when the base moves, so no automated signal existed at
#   all. Measured on the merged tree by the #325 reviewer:
#       $ alembic heads
#       engage0010 (head)
#       tailored0010 (head)
#       $ alembic upgrade head
#       FAILED: Multiple head revisions are present for given argument 'head'
#   `backend/docker-entrypoint.sh` runs `alembic upgrade head` on EVERY container
#   start, on both the FRESH and the ALEMBIC_MANAGED path — so this is not a CI
#   annoyance, it is a production backend that never finishes booting.
#
# It was caught by a human reading two diffs side by side. This script is that
# read, done mechanically, and it is dependency-free on purpose: no alembic
# import, no database, no Python — so it runs in the pre-push gate and in CI's
# Version Consistency job without a language setup step.
#
# Usage:
#   check_migration_heads.sh                     # the working tree only
#   check_migration_heads.sh --against origin/main   # the working tree UNIONED with that ref
#   check_migration_heads.sh --dir <path>        # override the versions directory
#
# `--against` is the load-bearing mode: a branch is almost always single-head on
# its own, and the fork is a property of the MERGE. The union takes every
# revision from both sides, keyed by revision id, with the working tree winning
# on conflict (that is the branch's intent for a revision it edited).
#
# KNOWN LIMITS, stated rather than implied:
#   * It reads `revision` / `down_revision` assignments textually. A migration
#     that computes its revision id at import time is invisible to it (none in
#     this repo; alembic's own template writes literals).
#   * `depends_on` is deliberately NOT a chain edge and is ignored.
#   * A merge revision (`down_revision = ("a", "b")`) is understood: every
#     quoted id in the tuple counts as a parent.
#   * `--against` UNIONS, so it cannot see a DELETION. A branch that removes a
#     migration the base still has gets it resurrected by the union and is
#     reported as a fork the real merge would not produce (#329 review, minor 4;
#     reproduced: base `a0001 -> b0002`, branch deletes `b0002` and adds `c0003`
#     on `a0001` -> alone `✓ one head`, `--against HEAD` -> `found 2`). Not fixed
#     rather than fixed badly: with `--dir` pointed at a partial directory — which
#     is exactly how the self-test drives it — "deleted on the branch" and "this
#     directory only holds a subset" are the same input. Deleting an applied
#     migration is also a thing this repo does not do (ids are stamped in
#     deployed databases). If it ever legitimately happens, run the checker
#     without `--against` and say so in the PR.
set -u

DIR_DEFAULT="backend/migrations/versions"
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
DIR=""
AGAINST=""

while [ $# -gt 0 ]; do
  case "$1" in
    --against) AGAINST="${2:-}"; shift 2 || exit 2 ;;
    --against=*) AGAINST="${1#--against=}"; shift ;;
    --dir) DIR="${2:-}"; shift 2 || exit 2 ;;
    --dir=*) DIR="${1#--dir=}"; shift ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    *) printf 'check_migration_heads: unknown argument %s\n' "$1" >&2; exit 2 ;;
  esac
done

[ -n "$DIR" ] || DIR="$ROOT/$DIR_DEFAULT"

if [ ! -d "$DIR" ]; then
  printf '✗ migration heads: %s is not a directory\n' "$DIR" >&2
  exit 1
fi

# revision id / parent ids out of ONE file's text on stdin.
# Anchored at column 0 so a docstring sentence beginning "revision. It creates …"
# (backend/migrations/versions/baseline0001_baseline_schema.py really has one)
# is not mistaken for an assignment.
parse_stream() {
  awk '
    function ids(s,   n, out, i, parts) {
      out = ""
      n = split(s, parts, /"/)
      # quoted tokens sit at the even indices of a split on the quote char
      for (i = 2; i <= n; i += 2) if (parts[i] != "") out = out " " parts[i]
      if (out == "") {
        n = split(s, parts, /'"'"'/)
        for (i = 2; i <= n; i += 2) if (parts[i] != "") out = out " " parts[i]
      }
      return out
    }
    /^revision[[:space:]]*(:[^=]*)?=/      { sub(/^[^=]*=/, "", $0); r = ids($0); next }
    /^down_revision[[:space:]]*(:[^=]*)?=/ { sub(/^[^=]*=/, "", $0); d = ids($0); next }
    END {
      gsub(/^ +| +$/, "", r)
      gsub(/^ +| +$/, "", d)
      if (r != "") printf "%s\t%s\n", r, d
    }
  '
}

# node[rev] = "file", parent[rev] = "p1 p2 …"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
: > "$TMP/edges"

collect_worktree() {
  local f
  for f in "$DIR"/*.py; do
    [ -e "$f" ] || continue
    case "$(basename "$f")" in __init__.py) continue ;; esac
    local line
    line="$(parse_stream < "$f")"
    [ -n "$line" ] && printf '%s\t%s\n' "$line" "$(basename "$f")" >> "$TMP/edges"
  done
}

collect_ref() {
  local ref="$1" reldir path line
  # The ref side is always read at the REPO-RELATIVE versions path. When --dir
  # points somewhere outside the repo (the self-test does exactly that, to hold
  # a branch's files without checking one out) the relative strip is a no-op and
  # would hand `git ls-tree` an absolute path that matches nothing — silently
  # turning the union back into a working-tree-only check, i.e. a gate that
  # cannot gate (lessons §18).
  reldir="${DIR#"$ROOT"/}"
  case "$reldir" in /*) reldir="$DIR_DEFAULT" ;; esac
  git -C "$ROOT" rev-parse --verify --quiet "$ref^{commit}" >/dev/null 2>&1 || {
    printf '✗ migration heads: cannot resolve git ref "%s"\n' "$ref" >&2
    exit 1
  }
  while IFS= read -r path; do
    case "$path" in *.py) ;; *) continue ;; esac
    case "$(basename "$path")" in __init__.py) continue ;; esac
    line="$(git -C "$ROOT" show "$ref:$path" 2>/dev/null | parse_stream)"
    [ -n "$line" ] && printf '%s\t%s\n' "$line" "$(basename "$path") @$ref" >> "$TMP/edges"
  done <<< "$(git -C "$ROOT" ls-tree -r --name-only "$ref" -- "$reldir" 2>/dev/null)"
}

# ORDER MATTERS: the ref is collected FIRST so the working tree's copy of a
# revision overwrites it. A branch that re-chains a revision must win over the
# base's older parent, otherwise the fix would still report the fork.
[ -n "$AGAINST" ] && collect_ref "$AGAINST"
collect_worktree

if [ ! -s "$TMP/edges" ]; then
  printf '✗ migration heads: no revisions found under %s\n' "$DIR" >&2
  exit 1
fi

RESULT="$(
  awk -F'\t' '
    { rev = $1; parents = $2; file = $3
      node[rev] = file                        # later wins: worktree over ref
      par[rev]  = parents
      order[rev] = 1
    }
    END {
      n = 0
      for (r in order) {
        split(par[r], ps, " ")
        for (i in ps) if (ps[i] != "" && ps[i] != "None") child[ps[i]] = child[ps[i]] " " r
      }
      for (r in order) {
        if (!(r in child)) { heads[++n] = r }
        split(par[r], ps, " ")
        for (i in ps) {
          p = ps[i]
          if (p != "" && p != "None" && !(p in order))
            printf "ORPHAN\t%s\t%s\t%s\n", r, p, node[r]
        }
      }
      printf "HEADS\t%d\n", n
      for (i = 1; i <= n; i++) printf "HEAD\t%s\t%s\n", heads[i], node[heads[i]]
      for (r in order) printf "REV\t%s\n", r
    }
  ' "$TMP/edges"
)"

HEAD_COUNT="$(printf '%s\n' "$RESULT" | awk -F'\t' '$1=="HEADS"{print $2}')"
REV_COUNT="$(printf '%s\n' "$RESULT" | awk -F'\t' '$1=="REV"' | wc -l | tr -d ' ')"
ORPHANS="$(printf '%s\n' "$RESULT" | awk -F'\t' '$1=="ORPHAN"{printf "  %s (in %s) points at unknown parent %s\n", $2, $4, $3}')"

FAIL=0

if [ -n "$ORPHANS" ]; then
  printf '✗ migration chain: a down_revision names a revision that does not exist\n'
  printf '%s\n' "$ORPHANS"
  FAIL=1
fi

if [ "${HEAD_COUNT:-0}" != "1" ]; then
  printf '✗ migration heads: expected exactly 1 head, found %s%s\n' \
    "${HEAD_COUNT:-0}" "$( [ -n "$AGAINST" ] && printf ' (working tree unioned with %s)' "$AGAINST")"
  printf '%s\n' "$RESULT" | awk -F'\t' '$1=="HEAD"{printf "  %s   (%s)\n", $2, $3}'
  cat <<'EOF'

`alembic upgrade head` REFUSES to run with more than one head, and
backend/docker-entrypoint.sh runs it on every container start — so this is a
backend that will not boot, not a lint opinion.

Fix: re-point the newer revision's `down_revision` at the other head (keep its
own revision id — a deployed database may already have it stamped), update its
docstring, then re-run:
    alembic heads          # exactly one
    alembic upgrade head && alembic downgrade -1 && alembic upgrade head

This is #323/#325: two branches each single-head alone, forked only once merged.
EOF
  FAIL=1
fi

[ "$FAIL" = "1" ] && exit 1

printf '✓ migration heads OK — %s revisions, exactly one head%s\n' \
  "$REV_COUNT" "$( [ -n "$AGAINST" ] && printf ' (working tree unioned with %s)' "$AGAINST")"
exit 0
