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

# --- #204: PROSE is not a command -------------------------------------------
# A quoted argument that spans newlines is data. Before the fix, the raw newline
# inside the quotes split the argument into segments, so a line of prose that
# merely STARTED with a destructive verb was inspected as an invocation — which
# blocked writing docs and PR comments about the very commands this guard exists
# for, training reflexive GUARD_DESTRUCTIVE=0 use. Strings are assembled from
# ${D}/${T} so this test file cannot block its own execution.
D="rm -rf"; DR="rm -R"; T="./data"
check "multiline quoted prose"    "gh pr comment 1 --body \"line one
$D $T was blocked
done\""                                                                             allow
check "multiline quoted -R prose" "gh issue comment 1 --body \"why
$DR \\\"$T\\\" slipped through
end\""                                                                              allow
check "heredoc writing prose"     "cat > notes.md <<'EOF'
Never run $D $T on prod.
EOF"                                                                                 allow
check "echo prose to a file"      "echo \"$D $T\" > notes.md"                       allow
# ...and the same shapes must STILL deny when they are genuinely executable:
check "heredoc fed to bash"       "bash <<'EOF'
$D $T
EOF"                                                                                 deny
check "heredoc fed to ssh"        "ssh host bash -s <<'EOF'
$D $T
EOF"                                                                                 deny

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

# --- MULTI-LINE QUOTED ARGUMENTS (#204) -------------------------------------
# This is the input class the #204 fix actually changed, and the one the first
# attempt at that fix got wrong: collapsing a quoted newline to a space fused a
# multi-line SCRIPT into one segment, so a benign leading `echo` hid everything
# after it and nine real destructions became allowed. The distinction is whether
# the quoted text is DATA (prose) or CODE (passed to a shell).
#
# Strings are assembled from $D/$T/$V parts so this file cannot block its own
# execution — the guard inspects the command that writes it, too.
D="rm -""rf"
DV="docker vol""ume rm"
DP="docker sys""tem prune"
DD="DR""OP DATA""BASE"
T="./""data"
V="mavrovde_db"

# CODE: newlines inside the quotes are command separators. Every one of these
# was DENIED before #204 and must stay denied.
check "sh -c: benign line then volume rm" "bash -c \"echo start
$DV $V\""                                                                        deny
check "sh -c: cd then rm -rf"             "sh -c \"cd /srv
$D $T\""                                                                         deny
check "eval: benign first line"           "eval \"echo hi
$DV $V\""                                                                        deny
check "sh -c single-quoted: prune"        "bash -c 'echo hi
$DP'"                                                                            deny
check "sh -c: sql database removal"       "bash -c \"echo ok
psql -c $DD mavrov\""                                                            deny
check "ssh: multi-line quoted body"       "ssh host \"cd /srv
$DV prod_db\""                                                                   deny
check "sh -c: destruction sandwiched"     "bash -c \"echo a
$D $T
echo b\""                                                                        deny
check "sh -c: leading newline"            "bash -c \"
$D $T\""                                                                         deny
check "unterminated quote then rm -rf"    "echo \"oops
$D $T"                                                                           deny

# DATA: the same newlines inside a quoted ARGUMENT are prose, and blocking them
# is what trained reflexive GUARD_DESTRUCTIVE=0 use.
check "multi-line quoted prose"           "gh pr comment 1 --body \"line one
$D $T was blocked
done\""                                                                          allow
check "heredoc written to a file"         "cat > notes.md <<'EOF'
$D $T is what #91 did.
EOF"                                                                             allow
check "heredoc fed to a shell"            "bash <<'EOF'
$D $T
EOF"                                                                             deny
check "heredoc fed to ssh"                "ssh host bash -s <<'EOF'
$DV $V
EOF"                                                                             deny

# --- HEREDOC OWNERSHIP AND FRAMING (#206 review round 2) --------------------
# Skipping a heredoc body is an EXEMPTION from a security control, so each of
# the three conditions that authorise it gets pinned here. Every case below was
# ALLOWED by the previous attempt at this fix.
#
# (a) The heredoc is consumed by the LAST command on the line, not the first.
#     Checking only the first token let a benign `echo` launder a shell heredoc —
#     the same first-token hole that broke the first version of this fix.
check "heredoc: echo && shell"       "echo 'cleaning up' && bash <<'EOF'
$DV $V
EOF"                                                                             deny
check "heredoc: pipe into shell"     "cat f | bash <<'EOF'
$DV $V
EOF"                                                                             deny
check "heredoc: echo ; sh"           "echo hi; sh <<'EOF'
$D $T
EOF"                                                                             deny

# (b) No terminator means we cannot know where the body ends, so nothing is
#     stripped. Skipping to EOF would have swallowed the destructive line.
check "heredoc: no terminator"       "cat > notes.md <<'EOF'
some docs
$DV $V"                                                                        deny

# (c) `<<` only counts as a redirect OUTSIDE quotes, and `<<<` is a here-string.
#     Otherwise merely WRITING ABOUT heredocs disarms the guard for every later
#     line — which is the #204 symptom turned into a bypass.
check "heredoc: << inside quotes"    "echo \"the <<HEREDOC form\"
cd /srv
$DV $V
$D $T
echo done"                                                                       deny
check "heredoc: grep for <<EOF"      "grep '<<EOF' notes.md
$DV $V"                                                                        deny
check "heredoc: commit msg <<EOF"    "git commit -m \"uses <<EOF here\"
$DV $V"                                                                        deny
check "heredoc: here-string <<<"     "cat <<<\"hello\"
$DV $V"                                                                        deny

# ssh option grammar must not decide whether the body is inspected. `-p 2222`
# etc. previously made the value look like the host and the host like the
# command, so the body was never reached.
check "ssh -p, multi-line body"      "ssh -p 2222 deploy@host \"cd /srv
$DV $V\""                                                                      deny
check "ssh -i, multi-line body"      "ssh -i ~/.ssh/k host \"echo hi
$D $T\""                                                                         deny
check "ssh -p, single-line body"     "ssh -p 2222 host \"$DV $V\""              deny
check "ssh -o, single-line body"     "ssh -o Port=22 host \"$DV $V\""           deny

# ...and the documents this exemption exists for are still allowed.
check "heredoc: tee to a file"       "tee notes.md <<'EOF'
$DV $V
EOF"                                                                             allow

# --- ESCAPED QUOTES (found by self-audit before round 3) --------------------
# A backslash escapes the next character everywhere except inside single quotes.
# Without that, `echo "a \" <<EOF"` looks like the quote closed early, the <<EOF
# reads as a real redirect, and a line of pure TEXT opens a heredoc that swallows
# the commands after it — a third instance of the same exemption-too-wide shape.
check "escaped quote fakes heredoc"  "echo \"a \\\" <<EOF\"
$DV $V
EOF"                                                                             deny
check "escaped quotes, no heredoc"   "echo \"say \\\"hi\\\" now\"
$DV $V"                                                                          deny
check "backslash inside single q"    "echo 'a \\ b'
$DV $V"                                                                          deny
check "prose with escaped quotes"    "gh pr comment 1 --body \"he said \\\"$D $T\\\" ok\"" allow

# --- THE HEREDOC EXEMPTION'S THREE CONDITIONS, PINNED (#206 review round 3) --
# Skipping a heredoc body is an exemption from a security control, so every
# condition that authorises it needs a test that fails without it. Round 3 showed
# `mask_quotes` was doing real work that NO case pinned — the terminator lookahead
# happened to cover the same inputs, so disabling the mask killed zero tests.

# The delimiter must be QUOTED. With an unquoted delimiter the shell EXPANDS the
# body, so `$(…)` and backticks in it execute — that body is code, not a
# document, and must stay inspected.
check "heredoc: unquoted delimiter"  "cat > n.md <<EOF
x=\$($D $T)
EOF"                                                                             deny
check "heredoc: dq delimiter ok"     "cat > notes.md <<\"EOF\"
$D $T here
EOF"                                                                             allow
check "heredoc: backslash delim ok"  "cat > notes.md <<\\EOF
$D $T here
EOF"                                                                             allow

# A `<<` inside a COMMENT is not a redirect.
check "heredoc: << in a comment"     "echo ok # <<'EOF'
$DV $V
EOF"                                                                             deny

# ...and a `<<` inside quotes is not either. This case exists specifically to
# pin mask_quotes: with the terminator present, the lookahead alone would let the
# body be stripped, so disabling the mask makes this case fail.
check "heredoc: << quoted, terminated" "grep \"<<'EOF'\" notes.md
$DV $V
EOF"                                                                             deny
check "heredoc: escaped quote + <<"  "printf \"a \\\" b <<'EOF'\"
$DV $V
EOF"                                                                             deny

# --- ONE QUOTING MODEL (#206 review round 4) --------------------------------
# mask_quotes and quote_split JOINTLY grant the heredoc exemption: the first
# decides whether a `<<` is a real redirect, the second decides whether every
# command on the line is a text tool. When only one of them understood backslash
# escapes they disagreed about what the line even was — `\"` looked like an
# unclosed quote to quote_split (so the line collapsed to one `echo`-led segment
# and read as "all text tools") while mask_quotes correctly saw a real redirect.
# An everyday commit message then hid a shell heredoc behind it.
#
# The existing "escaped quote + <<" case only covered an escaped quote FAKING an
# opener; these cover it HIDING the consuming shell, which 105/105 green missed.
check "escq: commit then shell hd"   "git commit -m \"escape the \\\" char\" ; bash <<'EOF'
$DV $V
EOF"                                                                             deny
check "escq: echo dq then shell hd"  "echo \\\" ; bash <<'EOF'
$DV $V
EOF"                                                                             deny
check "escq: echo sq then shell hd"  "echo \\' ; bash <<'EOF'
$DV $V
EOF"                                                                             deny
check "escq: printf then pipe sh"    "printf \\\" | sh <<'EOF'
$D $T
EOF"                                                                             deny
check "escq: inside a quoted arg"    "echo \"a \\\" b\" ; bash <<'EOF'
$DV $V
EOF"                                                                             deny
check "escq: then ssh bash -s"       "echo \"x \\\" y\" ; ssh host bash -s <<'EOF'
$DV $V
EOF"                                                                             deny
# ...and an escaped quote in an ordinary message stays allowed.
check "escq: commit msg, no heredoc" "git commit -m \"the \\\" char and $D $T\"" allow

# --- PACKED COMMANDS BEHIND A BENIGN TOKEN (#210) ---------------------------
# Two shapes where a destructive command hides behind something harmless. Both
# were allowed on `main` and are the same root cause as #204's rounds: the guard
# inspects the FIRST token of a segment, so anything that keeps the destruction
# out of first position slips past.

# (a) Separators packed INSIDE a shell wrapper's quoted argument. The outer
#     quote_split correctly protects them (they are inside quotes), so the whole
#     script arrives as one `echo`-led segment. The wrapper's argument is now
#     re-split as the script it is.
check "packed: ; inside bash -c"     "bash -c \"echo hi; $DV $V\""                deny
check "packed: && inside bash -c"    "bash -c \"echo hi && $D $T\""               deny
check "packed: || inside sh -c"      "sh -c \"false || $DV $V\""                  deny
check "packed: ; inside eval"        "eval \"echo hi; $DV $V\""                   deny
check "packed: nested bash -c"       "bash -c \"bash -c '$DV $V'\""               deny

# (b) A pipeline whose final stage is a shell reading stdin. `printf`/`echo` are
#     text tools and `bash` alone is not destructive, so neither segment looks
#     dangerous on its own — but the construct means "execute this text".
check "pipe: printf into bash"       "printf \"%s\" \"$DV $V\" | bash"            deny
check "pipe: echo into sh"           "echo \"$D $T\" | sh"                        deny
check "pipe: echo into sudo bash"    "echo \"$DV $V\" | sudo bash"                deny
check "pipe: echo into bash -s"      "echo \"$D $T\" | bash -s"                   deny

# ...and none of that may cost a false denial.
check "pipe: benign echo into bash"  "echo \"hello\" | bash"                      allow
check "pipe: curl into bash"         "curl -s https://example.com/i.sh | bash"    allow
check "packed: benign bash -c"       "bash -c \"echo hello world\""               allow
check "packed: prose in bash -c"     "bash -c \"echo 'note: $D $T is bad'\""      allow
check "pipe: grep into wc, no shell" "grep -r \"$D $T\" docs/ | wc -l"            allow

# --- A DOCUMENT IS ONLY A DOCUMENT UNTIL SOMETHING RUNS IT (#212) -----------
# The heredoc exemption exists so writing notes about destructive commands stops
# being blocked. But a heredoc redirected into a file that the SAME command then
# executes was never a document — it is a script written in two steps, and the
# exemption was skipping its body.
check "write then bash"              "cat > s.sh <<'EOF'
$DV $V
EOF
bash s.sh"                                                                       deny
check "write then sh"                "cat > s.sh <<'EOF'
$D $T
EOF
sh s.sh"                                                                         deny
check "write then source"            "cat > s.sh <<'EOF'
$DV $V
EOF
source s.sh"                                                                     deny
check "write then dot-space"         "cat > s.sh <<'EOF'
$DV $V
EOF
. s.sh"                                                                          deny
check "write, chmod, then ./"        "cat > s.sh <<'EOF'
$D $T
EOF
chmod +x s.sh && ./s.sh"                                                         deny
check "write to a path then bash"    "cat > ./tmp/s.sh <<'EOF'
$DV $V
EOF
bash ./tmp/s.sh"                                                                 deny
check "append then bash"             "cat >> s.sh <<'EOF'
$DV $V
EOF
bash s.sh"                                                                       deny

# ...and a document that is never executed stays allowed — including one that is
# merely read back, and one written alongside an unrelated script being run.
check "doc never executed"           "cat > notes.md <<'EOF'
$D $T happened
EOF"                                                                             allow
check "doc then cat it back"         "cat > notes.md <<'EOF'
$D $T
EOF
cat notes.md"                                                                    allow
check "doc then run OTHER script"    "cat > notes.md <<'EOF'
$D $T
EOF
bash other.sh"                                                                   allow

if [ "$fails" -eq 0 ]; then
  echo "All guard-destructive cases passed."
  exit 0
fi
echo "$fails guard-destructive case(s) FAILED."
exit 1
