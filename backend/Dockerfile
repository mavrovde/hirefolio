# Shared base stage for common OS dependencies
FROM python:3.12-slim AS base

WORKDIR /app

# Install runtime dependencies once in base.
# NOTE: the backend does NOT run any browser/Node tooling at runtime — LinkedIn
# ingest uses the pure-HTTP Python `linkedin-api` client (see
# app/services/linkedin.py, "no Node.js"), the entrypoint is Python/alembic, and
# the only subprocess is `pg_dump` (postgresql-client). The former
# Node.js + `playwright install --with-deps chromium` install was vestigial dead
# weight (~500MB+, the dominant build-time + a slow `type=gha` cache layer) and
# has been removed (#91). `libpq5` = asyncpg/libpq; `postgresql-client` = pg_dump
# (admin SQL export) + psql; `curl` kept for debugging/health probes.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    libpq5 \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Builder stage for compiling dependencies
FROM base AS builder

# Install build tools in builder stage
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    g++ \
    cargo \
    && rm -rf /var/lib/apt/lists/*

# Create and populate virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

# Copy requirements for dependency installation
COPY requirements.txt .

# Upgrade pip and install maturin with cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install maturin

# Install production dependencies
# linkedin-api PyPI wheel has broken entry point (lint = black:None) that pip rejects.
# Fix: download wheel, patch out the broken entry point using Python, install patched wheel.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip download linkedin-api==2.2.1 --no-deps -d /tmp/wheels && \
    mkdir -p /tmp/patched && \
    python -c "import zipfile; zin=zipfile.ZipFile('/tmp/wheels/linkedin_api-2.2.1-py3-none-any.whl','r'); zout=zipfile.ZipFile('/tmp/patched/linkedin_api-2.2.1-py3-none-any.whl','w'); [zout.writestr(i, b'') if i.filename.endswith('entry_points.txt') else zout.writestr(i, zin.read(i.filename)) for i in zin.infolist()]; zin.close(); zout.close()" && \
    pip install /tmp/patched/linkedin_api-2.2.1-py3-none-any.whl && \
    rm -rf /tmp/wheels /tmp/patched && \
    pip install -r requirements.txt

# Final runtime stage inherits from base
FROM base AS runtime

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

# CVE-2024-6345 (GHSA-cx63-2mw6-8hw5) is closed by the setuptools pin in
# requirements.txt (fixed in 70.0.0; we pin far past it). The historical sed
# that patched package_index.py in place was removed in #239: setuptools no
# longer ships that module (verified against the 83/84 wheels), and
# `find -exec … +` with zero matches exits 0 — the layer always "succeeded"
# while patching nothing, i.e. a dead security control giving false assurance.
# Guard: fail the build if the module ever reappears (a downgrade below the
# fixed version would resurface the vulnerable file).
RUN test -z "$(find /opt/venv -name package_index.py)" || { echo "package_index.py is back — setuptools downgraded below the CVE-2024-6345 fix?" >&2; exit 1; }

# Copy application code
COPY . .
RUN chmod +x docker-entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Alembic is the authoritative schema-management mechanism: the entrypoint
# runs `alembic upgrade head` before every container start (idempotent), then
# execs the app. See "Database Migrations" in the root README.md.
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
