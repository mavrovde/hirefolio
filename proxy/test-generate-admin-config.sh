#!/bin/sh
# Unit test for generate-admin-config.sh — asserts the real_ip + admin allowlist
# generator is CLOSED by default, opens on valid CIDRs, rejects malformed input,
# and never emits a blanket allow as the default. Deterministic; no Docker/topology
# needed. Run: sh proxy/test-generate-admin-config.sh
set -eu

DIR="$(cd "$(dirname "$0")" && pwd)"
GEN="$DIR/generate-admin-config.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail=0
check() { # desc, condition-result(0/1)
    if [ "$2" -eq 0 ]; then
        echo "  ok: $1"
    else
        echo "  FAIL: $1"
        fail=1
    fi
}
has()   { grep -Fq "$2" "$1" && echo 0 || echo 1; }   # file contains literal
hasnt() { grep -Fq "$2" "$1" && echo 1 || echo 0; }   # file lacks literal

run() { # runs generator with given env into $WORK (stderr -> $WORK/warn.log)
    ( cd "$WORK" && env "$@" TRUSTED_PROXY_CIDRS="${TRUSTED_PROXY_CIDRS:-172.16.0.0/12}" \
        "$GEN" "$WORK" 2> "$WORK/warn.log" )
}

ALLOW="$WORK/admin_allowlist.conf"
REALIP="$WORK/real_ip.conf"

echo "1) default (empty ADMIN_ALLOWED_CIDRS) -> CLOSED, no 'allow'"
env -u ADMIN_ALLOWED_CIDRS -u TRUSTED_PROXY_CIDRS "$GEN" "$WORK" 2>"$WORK/warn.log"
check "allowlist ends with deny all"                 "$(has "$ALLOW" 'deny all;')"
check "allowlist has NO allow line (closed default)" "$(hasnt "$ALLOW" 'allow ')"
check "real_ip trusts docker bridge default"         "$(has "$REALIP" 'set_real_ip_from 172.16.0.0/12;')"
check "real_ip reads X-Forwarded-For by default"     "$(has "$REALIP" 'real_ip_header X-Forwarded-For;')"
check "real_ip_recursive on"                         "$(has "$REALIP" 'real_ip_recursive on;')"

echo "2) valid ADMIN_ALLOWED_CIDRS -> allow lines + deny all"
ADMIN_ALLOWED_CIDRS="203.0.113.7 198.51.100.0/24" run
check "allow 203.0.113.7"        "$(has "$ALLOW" 'allow 203.0.113.7;')"
check "allow 198.51.100.0/24"    "$(has "$ALLOW" 'allow 198.51.100.0/24;')"
check "still ends with deny all" "$(has "$ALLOW" 'deny all;')"

echo "3) comma-separated list is accepted"
ADMIN_ALLOWED_CIDRS="10.0.0.1,10.0.0.2" run
check "allow 10.0.0.1"  "$(has "$ALLOW" 'allow 10.0.0.1;')"
check "allow 10.0.0.2"  "$(has "$ALLOW" 'allow 10.0.0.2;')"

echo "4) malformed entry is rejected (no injection), valid one kept"
ADMIN_ALLOWED_CIDRS="1.2.3.4 evil;deny all;allow all 5.6.7.8" run
check "valid 1.2.3.4 kept"                 "$(has "$ALLOW" 'allow 1.2.3.4;')"
check "valid 5.6.7.8 kept"                 "$(has "$ALLOW" 'allow 5.6.7.8;')"
check "injected 'allow all' NOT present"   "$(hasnt "$ALLOW" 'allow all')"
check "warned about invalid entry"         "$(has "$WORK/warn.log" 'ignoring invalid ADMIN_ALLOWED_CIDRS')"

echo "5) custom REAL_IP_HEADER + TRUSTED_PROXY_CIDRS honored"
REAL_IP_HEADER="X-Real-IP" TRUSTED_PROXY_CIDRS="192.168.0.0/16" ADMIN_ALLOWED_CIDRS="" run
check "trusts 192.168.0.0/16"       "$(has "$REALIP" 'set_real_ip_from 192.168.0.0/16;')"
check "reads X-Real-IP"             "$(has "$REALIP" 'real_ip_header X-Real-IP;')"

echo "6) 0.0.0.0/0 is emitted but loudly warned (test-only escape hatch)"
ADMIN_ALLOWED_CIDRS="0.0.0.0/0" run
check "allow 0.0.0.0/0 emitted"     "$(has "$ALLOW" 'allow 0.0.0.0/0;')"
check "warned about world-open"     "$(has "$WORK/warn.log" 'THE WORLD')"

echo ""
if [ "$fail" -eq 0 ]; then
    echo "ALL ADMIN-CONFIG GENERATOR TESTS PASSED"
else
    echo "ADMIN-CONFIG GENERATOR TESTS FAILED"
    exit 1
fi
