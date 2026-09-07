#!/usr/bin/env bash
# Self-test for scripts/check_compose_env.sh.
#
# The point of this file is the FAILING-FIRST case: a check that only ever
# reports OK is indistinguishable from a check that cannot fail (lessons §16/§18
# — "verify that your gates actually gate"). Every case below builds a throwaway
# repo skeleton in a temp dir, points the checker at it via CLAUDE_PROJECT_DIR,
# and asserts the exit code AND the message.
set -u

SCRIPT="$(cd "$(dirname "$0")" && pwd)/check_compose_env.sh"
pass=0; fail=0
ok()   { pass=$((pass+1)); printf '  ✓ %s\n' "$1"; }
bad()  { fail=$((fail+1)); printf '  ✗ %s\n     %s\n' "$1" "$2"; }

# Build a minimal repo: .env.example + backend/app/config.py + both compose files.
# $1 = temp dir, $2 = extra .env.example lines, $3 = extra compose env lines
skeleton() {
  d="$1"
  mkdir -p "$d/backend/app"
  { echo "# sample"; echo "# SITE_NAME=My Portfolio"; printf '%s\n' "$2"; } > "$d/.env.example"
  cat > "$d/backend/app/config.py" <<'PY'
class Settings(BaseSettings):
    site_name: str = "My Portfolio"
    translation_enabled: bool = True
    gemini_api_key: str = Field(default="", validation_alias="HIREFOLIO_GEMINI_API_KEY")
PY
  for f in docker-compose.yml docker-compose.prod.yml; do
    { echo "services:"
      echo "  db:"
      echo "    image: postgres"
      echo "  backend:"
      echo "    image: backend"
      echo "    environment:"
      echo "      - SITE_NAME=\${SITE_NAME:-My Portfolio}"
      printf '%s\n' "$3"
    } > "$d/$f"
  done
}

run() { CLAUDE_PROJECT_DIR="$1" bash "$SCRIPT" 2>&1; }

# --- 1. FAILING FIRST: the #298 shape — documented knob, not forwarded -------
d="$(mktemp -d)"; skeleton "$d" "# TRANSLATION_ENABLED=true" ""
out="$(run "$d")"; rc=$?
[ "$rc" -eq 1 ] && ok "documented-but-unforwarded key FAILS (rc=1)" \
  || bad "documented-but-unforwarded key FAILS" "rc=$rc, out=$out"
printf '%s' "$out" | grep -q 'never receives $TRANSLATION_ENABLED' \
  && ok "…and names the key + the file" || bad "names the key" "$out"
printf '%s' "$out" | grep -q 'docker-compose.prod.yml' \
  && ok "…and reports BOTH compose files" || bad "reports both files" "$out"
rm -rf "$d"

# --- 2. PASSING AFTER: the same repo with the forward added ------------------
d="$(mktemp -d)"; skeleton "$d" "# TRANSLATION_ENABLED=true" \
  "      - TRANSLATION_ENABLED=\${TRANSLATION_ENABLED:-true}"
out="$(run "$d")"; rc=$?
[ "$rc" -eq 0 ] && ok "adding the forward makes it PASS (rc=0)" \
  || bad "adding the forward makes it pass" "rc=$rc, out=$out"
rm -rf "$d"

# --- 3. Forwarded in dev but NOT in prod is still a failure (#296's shape) ---
d="$(mktemp -d)"; skeleton "$d" "# TRANSLATION_ENABLED=true" \
  "      - TRANSLATION_ENABLED=\${TRANSLATION_ENABLED:-true}"
: > "$d/docker-compose.prod.yml"
{ echo "services:"; echo "  backend:"; echo "    environment:"
  echo "      - SITE_NAME=\${SITE_NAME:-x}"; } > "$d/docker-compose.prod.yml"
out="$(run "$d")"; rc=$?
[ "$rc" -eq 1 ] && ok "dev-only forward still FAILS on prod" || bad "dev-only forward fails" "rc=$rc"
printf '%s' "$out" | grep -q 'docker-compose.yml — backend' \
  && bad "dev file wrongly reported" "$out" || ok "…and does not blame the dev file"
rm -rf "$d"

# --- 4. Namespaced alias (#141 HIREFOLIO_*) is understood -------------------
d="$(mktemp -d)"; skeleton "$d" "# HIREFOLIO_GEMINI_API_KEY=x" ""
out="$(run "$d")"; rc=$?
[ "$rc" -eq 1 ] && printf '%s' "$out" | grep -q 'HIREFOLIO_GEMINI_API_KEY' \
  && ok "validation_alias keys are part of the contract" || bad "alias keys" "rc=$rc out=$out"
rm -rf "$d"

# --- 5. A documented key that is NOT a Settings field is NOT reported --------
#     (keeps the check quiet: proxy/db/image keys are outside the contract)
d="$(mktemp -d)"; skeleton "$d" "# PUBLIC_SERVER_NAME=example.com" ""
out="$(run "$d")"; rc=$?
[ "$rc" -eq 0 ] && ok "non-Settings documented keys are ignored" || bad "non-Settings ignored" "$out"
rm -rf "$d"

# --- 6. A Settings field NOT documented in .env.example is NOT reported ------
#     (an internal default nobody is told to set is not a promise)
d="$(mktemp -d)"; skeleton "$d" "" ""
out="$(run "$d")"; rc=$?
[ "$rc" -eq 0 ] && ok "undocumented Settings fields are ignored" || bad "undocumented ignored" "$out"
rm -rf "$d"

# --- 7. The #297 shape: promised by README/setup.sh BEFORE .env.example ------
#     With .env.example as the only doc source this case is silent, which is
#     exactly why DOC_FILES is wider than one file.
d="$(mktemp -d)"; skeleton "$d" "" ""
printf 'Set TRANSLATION_ENABLED in your .env to disable it.\n' > "$d/README.md"
out="$(run "$d")"; rc=$?
[ "$rc" -eq 1 ] && ok "a knob promised only by README is still in the contract" \
  || bad "README as a doc source" "rc=$rc, out=$out"
printf '%s' "$out" | grep -q 'promised by: README.md' \
  && ok "…and the message names the file that promised it" || bad "names the doc source" "$out"
rm -rf "$d"

# --- 8. The REAL repo passes ------------------------------------------------
out="$(bash "$SCRIPT")"; rc=$?
[ "$rc" -eq 0 ] && ok "the real repository satisfies the contract" || bad "real repo" "$out"

printf '\ncheck_compose_env self-test: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
