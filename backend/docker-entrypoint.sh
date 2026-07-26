#!/bin/sh
# Alembic is the single source of truth for the schema (see issue #46). Every
# container start self-adopts the database into Alembic's tracking with NO
# manual step, then applies any pending migrations, before the app boots:
#
#   FRESH           - empty DB: `alembic upgrade head` creates the full schema.
#   PRE_ALEMBIC     - tables already exist (built by the old create_all, e.g.
#                     today's prod DB) but no alembic_version yet: stamp the
#                     baseline first (records the revision WITHOUT running any
#                     DDL), then upgrade head. Doing `upgrade head` directly
#                     here would try to CREATE TABLE objects that already
#                     exist and crash the app on startup.
#   ALEMBIC_MANAGED - alembic_version already exists: normal `upgrade head`.
#
# Re-running this on every restart is safe/idempotent: once a DB is stamped,
# it becomes ALEMBIC_MANAGED, and `alembic upgrade head` is a no-op at head.
set -e

STATE=$(python scripts/db_probe.py)
echo "[entrypoint] DB migration state detected: ${STATE}"

case "${STATE}" in
  PRE_ALEMBIC)
    echo "[entrypoint] Pre-Alembic database (tables exist, no alembic_version)."
    echo "[entrypoint] Stamping baseline0001 (no DDL), then upgrading to head..."
    alembic stamp baseline0001
    alembic upgrade head
    ;;
  FRESH|ALEMBIC_MANAGED)
    echo "[entrypoint] Running 'alembic upgrade head'..."
    alembic upgrade head
    ;;
  *)
    echo "[entrypoint] ERROR: unrecognized DB state '${STATE}' from scripts/db_probe.py" >&2
    exit 1
    ;;
esac

echo "[entrypoint] Migrations up to date. Starting app..."

exec "$@"
