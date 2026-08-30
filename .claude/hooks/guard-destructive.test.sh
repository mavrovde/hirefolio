#!/usr/bin/env bash
# Self-test for guard-destructive.sh (issue #116). Run: bash guard-destructive.test.sh
# Exits non-zero if any case regresses. Each case feeds a PreToolUse-shaped JSON
# on stdin and asserts the emitted permissionDecision (deny = blocked, allow = pass-through).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/guard-destructive.sh"
fails=0

check() { # desc cmd expect
  local desc="$1" cmd="$2" expect="$3" out dec
  out="$(printf '{"tool_input":{"command":%s}}' "$(jq -Rn --arg c "$cmd" '$c')" | bash "$HOOK")"
  dec="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision')"
  if [ "$dec" = "$expect" ]; then
    printf 'PASS  [%s]  %s\n' "$dec" "$desc"
  else
    printf 'FAIL  got=%s want=%s  %s\n     -> %s\n' "$dec" "$expect" "$desc" "$out"
    fails=$((fails + 1))
  fi
}

# --- must DENY (irreversible local/infra destruction) ---
check "docker volume rm"          'docker volume rm mavrovde_open-webui_data'        deny
check "docker volume prune"       'docker volume prune -f'                           deny
check "compose down -v"           'docker compose -f docker-compose.yml down -v'     deny
check "compose down --volumes"    'docker compose down --volumes'                    deny
check "docker system prune"       'docker system prune -af --volumes'                deny
check "docker image prune -a"     'docker image prune -a'                            deny
check "dropdb non-test"           'dropdb mavrov'                                    deny
check "DROP DATABASE non-test"    'psql -c "DROP DATABASE mavrov"'                   deny
check "rm -rf data dir"           'rm -rf ./data/pgdata'                             deny
check "rm -rf volumes path"       'sudo rm -rf /var/lib/volumes/ollama'             deny
check "rm -fr open-webui"         'rm -fr ./open-webui'                              deny
check "rm long-opts data dir"     'rm --recursive --force ./data/pgdata'             deny
check "rm -r --force volumes"     'rm -r --force /var/lib/volumes/ollama'            deny
check "rm -f ... -r data"         'rm -f -r ./data'                                  deny
check "rm -Rf data dir"           'rm -Rf ./data/pgdata'                             deny
# #188: the force flag is NOT what makes it dangerous — recursive alone destroys.
check "rm -R data (no -f)"        'rm -R ./data'                                     deny
check "rm -r pgdata (no -f)"      'rm -r ./data/pgdata'                              deny
check "rm --recursive volumes"    'rm --recursive /var/lib/volumes'                  deny
check "rm -R ollama dir"          'rm -R ~/ollama'                                   deny
check "rm -R open-webui"          'rm -R ./open-webui'                               deny
# Quoted paths are the same delete — a trailing quote must not defeat the boundary.
check "rm -R quoted data"         'rm -R "./data"'                                   deny
check "rm -rf single-quoted"      "rm -rf './data/pgdata'"                           deny
# ...and the near-miss paths must STILL be allowed with quotes in play.
check "rm -R data-table (near)"   'rm -R ./src/app/data-table'                       allow
check "rm -R quoted metadata"     'rm -R "build/metadata"'                           allow
check "rm -f single file in data" 'rm -f ./data/file.txt'                            allow
# ...but a recursive rm outside the protected paths must still be allowed.
check "rm -R dist (no -f)"        'rm -R frontend/dist'                              allow
check "rm -r node_modules"        'rm -r node_modules'                               allow

# --- must ALLOW (ordinary dev / test — never impede) ---
check "compose down (no -v)"      'docker compose down'                              allow
check "compose up"                'docker compose up -d'                             allow
check "dropdb test_*"             'dropdb test_mavrov'                               allow
check "DROP DATABASE test_*"      'psql -c "DROP DATABASE IF EXISTS test_mavrov"'    allow
check "rm -rf dist"               'rm -rf frontend/dist'                             allow
check "rm -rf node_modules"       'rm -rf node_modules'                              allow
check "rm long-opts node_modules" 'rm --recursive --force node_modules'              allow
check "rm -f only (no -r)"        'rm -f ./data/tmp.lock'                            allow
check "rm -rf .angular cache"     'rm -rf .angular/cache'                            allow
check "rm -rf scratchpad"         'rm -rf /private/tmp/claude-501/scratchpad/x'      allow
check "pytest"                    'cd backend && ./venv/bin/pytest -q'               allow
check "git push"                  'git push origin HEAD'                             allow
check "docker volume ls"          'docker volume ls'                                 allow
check "docker volume inspect"     'docker volume inspect mavrovde_db'                allow

# --- must ALLOW: destructive text is a mere ARGUMENT, not an invocation ---
check "git commit mentions rm"    'git commit -m "guard blocks docker volume rm now"' allow
check "grep for pattern"          "grep -rn 'docker volume rm' .claude/hooks"        allow
check "echo the pattern"          'echo "do not run docker system prune"'            allow
check "grep DROP DATABASE"        "grep -rn 'DROP DATABASE mavrov' backend"          allow
check "commit mentions rm -rf"    'git commit -m "note: never rm -rf ./data"'        allow

# --- must ALLOW: explicit inline authorization bypass ---
check "inline bypass volume rm"   'GUARD_DESTRUCTIVE=0 docker volume rm mavrovde_db' allow

# --- must still DENY when actually invoked in a later pipeline segment ---
check "chained volume rm"         'docker volume ls && docker volume rm mavrovde_db' deny
check "sudo volume rm"            'sudo docker volume rm mavrovde_db'                deny

# --- hardening (PR #132 review): wrapped/indirect invocations must still DENY ---
check "xargs volume rm (rm ALL)"  'docker volume ls -q | xargs docker volume rm'    deny
check "xargs -n1 volume rm"       'docker volume ls -q | xargs -n1 docker volume rm' deny
check "bash -c volume rm"         'bash -c "docker volume rm mavrovde_db"'          deny
check "sh -c system prune"        'sh -c "docker system prune -af"'                 deny
check "eval volume rm"            'eval "docker volume rm mavrovde_db"'             deny
check "env wrapper volume rm"     'env FOO=bar docker volume rm mavrovde_db'        deny
check "xargs rm -rf data"         'find . -name x | xargs rm -rf /var/data'         deny

# --- hardening: stray bypass token must NOT disarm a real later invocation ---
check "stray bypass no disarm"    'echo GUARD_DESTRUCTIVE=0 && docker volume rm x'  deny
# --- but a real LEADING per-segment bypass is honored ---
check "leading bypass honored"    'GUARD_DESTRUCTIVE=0 docker volume rm mavrovde_db' allow
check "chained leading bypass"    'docker volume ls && GUARD_DESTRUCTIVE=0 docker volume rm x' allow
# --- xargs of a benign command still ALLOWed ---
check "xargs benign"              'ls *.log | xargs rm'                             allow

# --- quote-aware: a separator INSIDE a quoted arg is text, not an invocation ---
check "commit msg quoted pipe"    'git commit -m "idiom: docker volume ls | xargs docker volume rm"' allow
check "echo quoted pipe rm"       'echo "run: cat x | xargs rm -rf /data"'         allow
# --- but a REAL unquoted pipe to a destructive command still DENYs ---
check "real pipe xargs volume rm" 'cat volumes.txt | xargs docker volume rm'       deny

if [ "$fails" -eq 0 ]; then
  echo "All guard-destructive cases passed."
  exit 0
fi
echo "$fails guard-destructive case(s) FAILED."
exit 1
