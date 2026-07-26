#!/bin/sh
# Alembic is the single source of truth for the schema (see issue #46 /
# docs/backend/migrations.md). Every container start applies any pending
# migrations before the app boots; `alembic upgrade head` is a no-op when
# already at head, so this is safe to run unconditionally on every restart.
set -e

echo "[entrypoint] Running 'alembic upgrade head'..."
alembic upgrade head
echo "[entrypoint] Migrations up to date. Starting app..."

exec "$@"
