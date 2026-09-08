#!/usr/bin/env bash
# Self-test for scripts/check_no_pii.sh — BOTH of its contracts.
#
# The point of this file is the FAILING-FIRST case. Check A (PII) shipped for two
# releases with no self-test at all, and check B (#313 de-branding) is a *new*
# gate: a gate that has never been observed to fail is indistinguishable from a
# gate that cannot fail (lessons §16/§18 — "verify that your gates actually
# gate"). Every case below builds a throwaway git repo in a temp dir, points the
# checker at it via CLAUDE_PROJECT_DIR, and asserts the exit code AND the message.
set -u

SCRIPT="$(cd "$(dirname "$0")" && pwd)/check_no_pii.sh"
pass=0; fail=0
ok()  { pass=$((pass+1)); printf '  ✓ %s\n' "$1"; }
bad() { fail=$((fail+1)); printf '  ✗ %s\n     %s\n' "$1" "$2"; }

# A minimal repo carrying every in-scope surface plus two out-of-scope ones, all
# clean. $1 = temp dir. Callers then dirty exactly one file.
skeleton() {
  d="$1"
  mkdir -p "$d/docs/retrospectives" "$d/docs/agent-runs" "$d/docs/wiki" \
           "$d/.claude/agents" "$d/agents" "$d/.github/prompts" "$d/importer"
  echo "# Hirefolio" > "$d/README.md"
  echo "deploy Hirefolio at <your-domain>" > "$d/docs/DEPLOYMENT.md"
  echo "see <your-domain>" > "$d/docs/wiki/production-deployment.md"
  echo "v1.0.0 retro" > "$d/docs/retrospectives/v1.0.0.md"
  echo "run log" > "$d/docs/agent-runs/run.md"
  echo "You work on Hirefolio." > "$d/.claude/agents/backend-dev.md"
  echo "# SITE_URL=https://example.com" > "$d/.env.example"
  echo "You are part of the Hirefolio delivery team." > "$d/agents/PLAYBOOK.md"
  echo "Hirefolio testing guide." > "$d/README_TESTING.md"
  echo "Report at https://github.com/mavrovde/hirefolio/security/advisories/new" > "$d/SECURITY.md"
  echo "A LinkedIn -> Hirefolio content pipeline." > "$d/.github/copilot-instructions.md"
  echo "Prepare and check a release of Hirefolio." > "$d/.github/prompts/release-check.prompt.md"
  echo "# Dependabot version updates for Hirefolio" > "$d/.github/dependabot.yml"
  echo "Pushes your posts into your Hirefolio backend." > "$d/importer/README.md"
  # Surfaces round 2 proved unguarded under the old INCLUDE list — plus the rest
  # of the same class (every legacy per-tool rule file, every instructions file).
  mkdir -p "$d/.github/instructions" "$d/scraper"
  for g in AGENTS.md AI.md .cline.md .clauderules .cursorrules .geminirules .windsurfrules; do
    echo "See CLAUDE.md; this project is Hirefolio." > "$d/$g"
  done
  echo "Images publish to ghcr.io/mavrovde/hirefolio-*." > "$d/.github/instructions/infra-ci.instructions.md"
  echo "Scrape, then import into your Hirefolio backend." > "$d/scraper/WORKFLOW.md"
  # Excluded classes: each must keep the domain WITHOUT tripping the guard.
  mkdir -p "$d/specs/done" "$d/proxy" "$d/backend/app" "$d/agents/common" "$d/.github/workflows"
  echo "## v1.0.0 — moved off mavrov.de" > "$d/CHANGELOG.md"
  echo "  - PUBLIC_SERVER_NAME=\${PUBLIC_SERVER_NAME:-mavrov.de}" > "$d/docker-compose.yml"
  echo "spec: import into mavrov.de" > "$d/specs/done/06-importer.md"
  echo "the maintainer deploys it at mavrov.de" > "$d/CLAUDE.md"
  echo ': "${PUBLIC_SERVER_NAME:=mavrov.de}"' > "$d/proxy/entrypoint.sh"
  echo "# defaults preserve the mavrov.de hostnames" > "$d/proxy/default.conf.template"
  echo "          PUBLIC_URL: 'https://mavrov.de'" > "$d/.github/workflows/deploy.yml"
  echo '    cors_origins: str = "https://mavrov.de"' > "$d/backend/app/config.py"
  echo '"""A2A team for mavrov.de."""' > "$d/agents/common/roster.py"
  echo '"""LinkedIn -> mavrov.de importer."""' > "$d/importer/core.py"
  echo '{"headers": {"Host": "mavrov.de"}}' > "$d/verify_proxy_routes.py"
  ( cd "$d" && git init -q . && git add -A ) >/dev/null 2>&1
}

# $1 = temp dir. Re-stages so newly written files are visible to `git grep`.
run() { ( cd "$1" && git add -A >/dev/null 2>&1; CLAUDE_PROJECT_DIR="$1" bash "$SCRIPT" 2>&1 ); }

# --- 1. FAILING FIRST: unannotated domain on a guidance surface -------------
d="$(mktemp -d)"; skeleton "$d"
echo "Point your DNS at mavrov.de and you are done." >> "$d/README.md"
out="$(run "$d")"; rc=$?
[ "$rc" -eq 1 ] && ok "unannotated maintainer domain in README FAILS (rc=1)" \
  || bad "unannotated domain fails" "rc=$rc, out=$out"
printf '%s' "$out" | grep -q 'De-brand guard' \
  && ok "…and says which guard tripped" || bad "names the guard" "$out"
printf '%s' "$out" | grep -q 'README.md' \
  && ok "…and names the offending file" || bad "names the file" "$out"
rm -rf "$d"

# --- 2. PASSING AFTER: the product voice ------------------------------------
d="$(mktemp -d)"; skeleton "$d"
echo "Point your DNS at <your-domain> and you are done." >> "$d/README.md"
out="$(run "$d")"; rc=$?
[ "$rc" -eq 0 ] && ok "the placeholder rewrite PASSES (rc=0)" \
  || bad "placeholder passes" "rc=$rc, out=$out"
rm -rf "$d"

# --- 3. The three annotations are the ONLY way to keep the domain -----------
for marker in \
  "the maintainer's install <!-- de-brand:canonical: the one sanctioned aside --> at mavrov.de" \
  "it was /opt/mavrov.de <!-- de-brand:historical: the pre-#310 default -->" \
  "pre-rename images live at ghcr.io/mavrovde/mavrov.de-backend"
do
  d="$(mktemp -d)"; skeleton "$d"
  printf '%s\n' "$marker" >> "$d/README.md"
  out="$(run "$d")"; rc=$?
  [ "$rc" -eq 0 ] && ok "annotated line accepted: ${marker:0:38}…" \
    || bad "annotated line accepted: $marker" "rc=$rc, out=$out"
  rm -rf "$d"
done

# --- 3b. NEGATIVE direction: an INCIDENTAL marker word must NOT exempt -------
#     Round 1 of #318 matched three BARE words against the whole `git grep`
#     output line. The reviewer walked all three of these through it green — the
#     third being a straight REVERT of the README row this change fixed, exempted
#     because the cell says "canonical". "canonical" and "historical" are ordinary
#     English in this repo (21 in-scope lines already use "canonical" innocently),
#     so the ONLY thing that may exempt a line is the `de-brand:` namespace.
for prose in \
  "Set SSR to advertise mavrov.de as the canonical URL for every page." \
  "The historical posts feed is served from mavrov.de/blog." \
  "| PUBLIC_SERVER_NAME | .env | mavrov.de www.mavrov.de | the canonical fallback |" \
  "mavrov.de is the instance <!-- DE-BRAND:CANONICAL --> — marker in the wrong case."
do
  d="$(mktemp -d)"; skeleton "$d"
  printf '%s\n' "$prose" >> "$d/README.md"
  out="$(run "$d")"; rc=$?
  [ "$rc" -eq 1 ] && ok "incidental marker does NOT exempt: ${prose:0:36}…" \
    || bad "incidental marker must not exempt: $prose" "rc=$rc, out=$out"
  rm -rf "$d"
done

# --- 3c. NEGATIVE direction: the marker may not live in the PATH -------------
#     `git grep -in` emits `path:line:content`; filtering the whole line made
#     every file under a `canonical`/`historical`-named directory exempt forever.
#     The third path carries the FULL namespaced marker in a directory name — it
#     is the case that falsifies the fix itself: stripping the prefix textually
#     cannot handle a path containing `:`, so the checker must read the file.
for p in docs/canonical-urls/setup.md docs/historical-notes/hosting.md \
         'docs/de-brand:historical-notes/hosting.md'
do
  d="$(mktemp -d)"; skeleton "$d"
  mkdir -p "$d/$(dirname "$p")"
  echo "Point your DNS at mavrov.de and you are done." > "$d/$p"
  out="$(run "$d")"; rc=$?
  [ "$rc" -eq 1 ] && ok "a marker word in the PATH does not exempt: $p" \
    || bad "path-level exemption hole: $p" "rc=$rc, out=$out"
  rm -rf "$d"
done

# --- 4. EVERY in-scope surface is actually scanned ---------------------------
#     A scope list is a claim; an unscanned entry is a silent hole. Rounds 1 AND 2
#     of #318 both found branded, permanently-unguarded surfaces because the scope
#     was an INCLUDE list — round 2's positive control (append the domain, watch
#     the guard stay green) caught AGENTS.md, AI.md, .cline.md,
#     .github/instructions/*, scraper/WORKFLOW.md. The scope is now inverted, so
#     this loop asserts the *whole class*, not a hand-maintained subset.
for f in README.md docs/DEPLOYMENT.md docs/wiki/production-deployment.md \
         .claude/agents/backend-dev.md .env.example agents/PLAYBOOK.md \
         README_TESTING.md SECURITY.md .github/copilot-instructions.md \
         .github/prompts/release-check.prompt.md .github/dependabot.yml \
         importer/README.md \
         AGENTS.md AI.md .cline.md .clauderules .cursorrules .geminirules \
         .windsurfrules .github/instructions/infra-ci.instructions.md \
         scraper/WORKFLOW.md
do
  d="$(mktemp -d)"; skeleton "$d"
  echo "deploy it at mavrov.de" >> "$d/$f"
  out="$(run "$d")"; rc=$?
  [ "$rc" -eq 1 ] && ok "in scope: $f" || bad "in scope: $f" "rc=$rc, out=$out"
  rm -rf "$d"
done

# --- 4b. FAIL CLOSED: a file nobody ever listed is guarded from birth --------
#     This is the case an include list can never satisfy, and the reason the scope
#     was inverted. None of these paths appears anywhere in the checker.
for f in docs/BRAND-NEW.md .github/instructions/newthing.instructions.md \
         .github/workflows/newthing.yml proxy/newthing.conf \
         some/dir/nobody/listed/guide.md .aiderrules
do
  d="$(mktemp -d)"; skeleton "$d"
  mkdir -p "$d/$(dirname "$f")"
  echo "Point your DNS at mavrov.de and you are done." > "$d/$f"
  out="$(run "$d")"; rc=$?
  [ "$rc" -eq 1 ] && ok "guarded from birth (never listed): $f" \
    || bad "new file unguarded: $f" "rc=$rc, out=$out"
  rm -rf "$d"
done

# --- 5. Historical + runtime + application surfaces stay OUT of scope --------
#     History must not be rewritten, a runtime default must not be repointed, and
#     application code is a separate effort. Each entry here is a DEFERRAL of #313
#     made executable — if one is ever de-branded, its exclusion comes off and the
#     matching case here flips.
for f in docs/retrospectives/v1.0.0.md docs/agent-runs/run.md CHANGELOG.md \
         specs/done/06-importer.md CLAUDE.md \
         docker-compose.yml proxy/entrypoint.sh proxy/default.conf.template \
         .github/workflows/deploy.yml \
         backend/app/config.py agents/common/roster.py importer/core.py \
         verify_proxy_routes.py
do
  d="$(mktemp -d)"; skeleton "$d"
  echo "we shipped mavrov.de v1.0.0 that day" >> "$d/$f"
  out="$(run "$d")"; rc=$?
  [ "$rc" -eq 0 ] && ok "out of scope: $f" || bad "out of scope: $f" "rc=$rc, out=$out"
  rm -rf "$d"
done

# --- 5b. The agents/ exclusion is NARROW, not the whole directory ------------
#     agents/PLAYBOOK.md is the shared agent charter and must stay guarded even
#     though its neighbours in agents/ are excluded application code.
d="$(mktemp -d)"; skeleton "$d"
echo "the mavrov.de delivery team" >> "$d/agents/PLAYBOOK.md"
out="$(run "$d")"; rc=$?
[ "$rc" -eq 1 ] && ok "agents/PLAYBOOK.md stays in scope beside excluded agents/ code" \
  || bad "PLAYBOOK excluded with the rest of agents/" "rc=$rc, out=$out"
rm -rf "$d"

# --- 6. Check A still gates, and the two checks are independent -------------
d="$(mktemp -d)"; skeleton "$d"
# The identifier is ASSEMBLED, never written literally: this file is itself
# scanned by the check it tests, so a literal one trips check A for real. It did
# — on the first push attempt of #313, which is the gate working as intended.
# Excluding this file from check A would have been the weaker fix.
pii="serg"".mavrov@example.com"
echo "contact $pii" >> "$d/docs/DEPLOYMENT.md"
out="$(run "$d")"; rc=$?
[ "$rc" -eq 1 ] && ok "PII identifier still FAILS (rc=1)" || bad "PII fails" "rc=$rc, out=$out"
printf '%s' "$out" | grep -q '✗ PII guard' \
  && ok "…reported by check A" || bad "check A reports" "$out"
printf '%s' "$out" | grep -q '✓ De-brand guard' \
  && ok "…while check B independently passes (A failing does not skip B)" \
  || bad "B runs after A fails" "$out"
rm -rf "$d"

# --- 7. A clean repo passes both --------------------------------------------
d="$(mktemp -d)"; skeleton "$d"
out="$(run "$d")"; rc=$?
[ "$rc" -eq 0 ] && ok "a clean repo passes both checks" || bad "clean repo" "rc=$rc, out=$out"
rm -rf "$d"

# --- 8. The REAL repository satisfies both contracts -------------------------
out="$(bash "$SCRIPT")"; rc=$?
[ "$rc" -eq 0 ] && ok "the real repository satisfies both contracts" || bad "real repo" "$out"

printf '\ncheck_no_pii self-test: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
