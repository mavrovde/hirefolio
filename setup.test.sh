#!/usr/bin/env bash
# Self-test for setup.sh's .env contract (#61/#256): the helpers that touch
# the user's secrets file must be pinned, same precedent as
# test-bump-version.sh and the hook self-tests. Runs hermetically in a temp
# dir — no docker, no network.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
PASS=0; FAIL=0

# Extract ONLY the helper functions from setup.sh (everything between the
# helpers marker and the first numbered step), so the test never executes the
# stack-boot part.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
sed -n '/^# --- helpers/,/^# --- 1\./p' "$HERE/setup.sh" | sed '$d' > "$TMP/helpers.sh"

run_case() { # desc, setup-fn, assert-fn
  local desc="$1" setup_fn="$2" assert_fn="$3"
  local dir; dir="$(mktemp -d "$TMP/case.XXXXXX")"
  (
    cd "$dir" || exit 9
    export ENV_FILE="$dir/.env"
    # shellcheck disable=SC1091
    . "$TMP/helpers.sh"
    "$setup_fn" && "$assert_fn"
  )
  if [ $? -eq 0 ]; then PASS=$((PASS+1)); echo "PASS  $desc";
  else FAIL=$((FAIL+1)); echo "FAIL  $desc"; fi
}

# --- cases -------------------------------------------------------------------

c1_setup() { printf 'A=1\n' > "$ENV_FILE"; set_env B hello; }
c1_assert() { [ "$(get_env B)" = "hello" ] && [ "$(get_env A)" = "1" ]; }
run_case "append adds a new key, existing kept" c1_setup c1_assert

c2_setup() { printf 'OWNER_NAME=Bob' > "$ENV_FILE"; set_env JWT_SECRET_KEY sekret; }  # NO trailing newline
c2_assert() {
  [ "$(get_env OWNER_NAME)" = "Bob" ] && [ "$(get_env JWT_SECRET_KEY)" = "sekret" ] \
    && ! grep -q 'BobJWT' "$ENV_FILE"
}
run_case "no-trailing-newline file is mended, both values intact (#256 blocker 2)" c2_setup c2_assert

c3_setup() { printf 'K=first\n' > "$ENV_FILE"; set_env K second; }
c3_assert() { [ "$(get_env K)" = "first" ]; }
run_case "existing non-empty value is NEVER overwritten" c3_setup c3_assert

c4_setup() { printf 'K=\r\n' > "$ENV_FILE"; set_env K realvalue; }
c4_assert() { [ "$(get_env K)" = "realvalue" ]; }
run_case "whitespace/CR-only value counts as UNSET — no 1-byte secrets (#256 finding 4)" c4_setup c4_assert

c5_setup() { printf '# K=commented\n' > "$ENV_FILE"; set_env K real; }
c5_assert() { [ "$(get_env K)" = "real" ]; }
run_case "commented assignment is ignored" c5_setup c5_assert

c6_setup() { printf 'K=a=b=c\n' > "$ENV_FILE"; :; }
c6_assert() { [ "$(get_env K)" = "a=b=c" ]; }
run_case "values containing '=' round-trip" c6_setup c6_assert

c7_setup() { printf '  export K=fromexport\n' > "$ENV_FILE"; :; }
c7_assert() { [ "$(get_env K)" = "fromexport" ]; }
run_case "leading whitespace + export prefix are accepted" c7_setup c7_assert

c8_setup() { printf 'K=one\nK=two\n' > "$ENV_FILE"; :; }
c8_assert() { [ "$(get_env K)" = "two" ]; }
run_case "last uncommented assignment wins (compose semantics)" c8_setup c8_assert

c9_setup() { printf 'A=1\n' > "$ENV_FILE"; set_env B x; set_env B y; set_env C z; }
c9_assert() {
  [ "$(grep -c '^B=' "$ENV_FILE")" = "1" ] && [ "$(get_env B)" = "x" ] && [ "$(get_env C)" = "z" ]
}
run_case "re-running set_env is idempotent (no duplicate keys)" c9_setup c9_assert

c10_setup() { : > "$ENV_FILE"; set_env K v; }
c10_assert() { [ "$(get_env K)" = "v" ] && [ "$(head -c1 "$ENV_FILE")" = "K" ]; }
run_case "empty file gains no spurious leading newline" c10_setup c10_assert


c11_setup() { :; }
c11_assert() {
  # Reviewer-authored (#256 round 2): a wizard-generated value that the dev
  # compose does not forward is a credential the user cannot use.
  local be; be="$(awk '/^  backend:/,/^  frontend:/' "$HERE/docker-compose.yml")"
  local k rc=0
  for k in $(grep -oE '^[[:space:]]*set_env[[:space:]]+[A-Z_]+' "$HERE/setup.sh" | awk '{print $2}' | sort -u); do
    printf '%s\n' "$be" | grep -q -- "- $k=\${$k" || { echo "    $k is not forwarded to the backend container"; rc=1; }
  done
  return $rc
}
run_case "every key setup.sh writes is forwarded by the dev compose (#256 blocker 1)" c11_setup c11_assert

echo "----"
echo "setup.sh helper self-test: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
