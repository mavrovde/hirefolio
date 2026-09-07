#!/usr/bin/env bash
# One-command setup (#61): clone → answer a couple of prompts → running site.
#
#   ./setup.sh                 interactive (prompts for identity)
#   ./setup.sh --defaults      non-interactive demo setup (Jane Doe persona)
#
# What it does, idempotently:
#   1. creates .env from .env.example if missing
#   2. generates strong secrets (JWT signing key, admin password) if unset
#   3. records your identity (owner name / site name / URL) for the runtime
#      site config (#65)
#   4. brings the Docker stack up and waits for the backend health gate
#
# Safe to re-run: existing non-empty values in .env are NEVER overwritten.
# Works on macOS (bash 3.2, BSD userland) and Linux.
#
# SCOPE: this is the LOCAL QUICKSTART — it boots the DEV compose stack
# (local builds, dev ports, ephemeral-JWT default). For a real server use
# docs/DEPLOYMENT.md ("First deploy (clean server)"), which walks the PROD
# compose file, prebuilt images, and hardened settings.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"
NONINTERACTIVE=0
[ "${1:-}" = "--defaults" ] && NONINTERACTIVE=1

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN:\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mFATAL:\033[0m %s\n' "$*" >&2; exit 1; }

# --- 0. prerequisites -------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker is required — install Docker Desktop / Engine first."
docker compose version >/dev/null 2>&1 || die "the 'docker compose' plugin is required."
docker info >/dev/null 2>&1 || die "the Docker daemon is not running — start it and re-run."
command -v openssl >/dev/null 2>&1 || die "openssl is required to generate secrets."
command -v curl >/dev/null 2>&1 || die "curl is required for the health gate."
[ -x "$ROOT/manage.sh" ] || die "manage.sh not found/executable — run from the repo root."

# --- helpers ----------------------------------------------------------------
# get_env KEY -> current uncommented value in .env ('' if absent, empty, or
# whitespace/CR-only — a "\r" left by a CRLF editor must NOT count as a set
# secret, or a 1-byte signing key sails through; #256 review finding 4).
# Accepts optional leading whitespace and an `export ` prefix on the line.
get_env() {
  [ -f "$ENV_FILE" ] || { echo ""; return; }
  # last uncommented assignment wins, matching docker compose semantics
  awk -v k="$1" '
    /^[[:space:]]*#/ { next }
    {
      line = $0
      sub(/^[[:space:]]*/, "", line)
      sub(/^export[[:space:]]+/, "", line)
      eq = index(line, "=")
      if (eq > 1 && substr(line, 1, eq - 1) == k) {
        v = substr(line, eq + 1)
        gsub(/[[:space:]\r]+$/, "", v)
        gsub(/^[[:space:]]+/, "", v)
        val = v
      }
    }
    END { print val }
  ' "$ENV_FILE"
}

# set_env KEY VALUE — append (never rewrite the file wholesale; preserves
# every existing line — the #175 rollout learned this the hard way)
set_env() {
  if [ -n "$(get_env "$1")" ]; then
    return 0  # existing value is authoritative; never overwrite
  fi
  # A file without a trailing newline would glue the new KEY= onto the last
  # line, corrupting BOTH values (#256 review blocker 2) — mend it first.
  if [ -s "$ENV_FILE" ] && [ "$(tail -c 1 "$ENV_FILE" | wc -l | tr -d ' ')" -eq 0 ]; then
    printf '\n' >> "$ENV_FILE"
  fi
  printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"
}

ask() { # ask PROMPT DEFAULT -> stdout
  local ans
  if [ "$NONINTERACTIVE" = "1" ]; then echo "$2"; return; fi
  printf '%s [%s]: ' "$1" "$2" > /dev/tty
  read -r ans < /dev/tty || ans=""
  echo "${ans:-$2}"
}

# --- 1. .env ----------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  say "Creating .env from .env.example"
  cp "$ROOT/.env.example" "$ENV_FILE"
else
  say ".env exists — keeping it (values already set are never overwritten)"
fi
# Always (not only on create): the file holds generated secrets either way.
chmod 600 "$ENV_FILE"

# --- 2. secrets -------------------------------------------------------------
if [ -z "$(get_env JWT_SECRET_KEY)" ]; then
  say "Generating JWT signing secret"
  set_env JWT_SECRET_KEY "$(openssl rand -hex 32)"
fi
ADMIN_PW="$(get_env ADMIN_PASSWORD)"
if [ -z "$ADMIN_PW" ]; then
  say "Generating admin password"
  ADMIN_PW="$(openssl rand -base64 18 | tr -d '/+=' )"
  set_env ADMIN_PASSWORD "$ADMIN_PW"
  NEW_ADMIN_PW=1
else
  NEW_ADMIN_PW=0
fi

# --- 3. identity (runtime site config, #65) ---------------------------------
if [ -z "$(get_env OWNER_NAME)" ]; then
  say "Site identity (shown to visitors; change any time in .env — no rebuild)"
  set_env OWNER_NAME     "$(ask 'Your name'            'Jane Doe')"
  set_env OWNER_HEADLINE "$(ask 'Your headline'        'Software Engineer')"
  set_env SITE_NAME      "$(ask 'Site name'            'My Portfolio')"
  set_env SITE_URL       "$(ask 'Public URL'           'http://localhost:4200')"
fi

# --- 4. bring the stack up ---------------------------------------------------
say "Starting the Docker stack (db, ollama, backend, frontend, proxy)"
"$ROOT/manage.sh" start

say "Waiting for the backend health gate"
ok=0
for i in $(seq 1 60); do
  if curl -s -m 5 "http://localhost:8000/api/app/health" 2>/dev/null | grep -q healthy; then ok=1; break; fi
  sleep 5
done
if [ "$ok" != "1" ]; then
  warn "Backend not healthy after 5 min — check './manage.sh logs backend'."
else
  say "Backend healthy."
fi

# --- 5. done -----------------------------------------------------------------
echo
say "Setup complete."
echo "  Public site : http://localhost:4200"
echo "  Admin panel : http://admin.localhost:4200 (user: admin; loopback is"
echo "                always allowed — see ADMIN_ALLOWED_CIDRS in .env.example)"
if [ "$NEW_ADMIN_PW" = "1" ]; then
  echo "  Admin password: $ADMIN_PW   (also stored in .env — keep it safe)"
else
  echo "  Admin password: (unchanged, from your .env)"
fi
echo
echo "Phone pings: set HIREFOLIO_TELEGRAM_BOT_TOKEN + _CHAT_ID for instant Telegram"
echo "notifications (2 minutes with @BotFather; see README). Slack/ntfy: HIREFOLIO_NOTIFY_WEBHOOK_URL."
echo "Email: dev captures everything in Mailpit (http://localhost:8025) with zero"
echo "config; for real delivery set SMTP_* to a provider, or see the opt-in"
echo "'mail' compose profile in docs/DEPLOYMENT.md (deliverability caveats there)."
echo
echo "Make it yours: edit the identity block in .env (OWNER_NAME, SITE_URL, ...)"
echo "and upload your own profile data + CV in the admin panel — no code edits."
