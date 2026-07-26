# Shared base stage for common OS dependencies
FROM python:3.12-slim AS base

WORKDIR /app

# Install runtime dependencies once in base
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    libpq5 \
    postgresql-client \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g playwright dotenv cross-env \
    && npx playwright install --with-deps chromium \
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

# Patch setuptools vulnerability (CVE-2024-6345 / GHSA-cx63-2mw6-8hw5) in package_index.py
# The vulnerable line is: name = name.replace('..', '.').replace('\\', '_')
# We replace it with: name = name.replace('../', '').replace('..\\', '').replace('\\', '_')
RUN find /opt/venv -name "package_index.py" -exec sed -i "s/name.replace('..', '.').replace('\\\\', '_')/name.replace('..\/', '').replace('..\\\\\\\\', '').replace('\\\\', '_')/g" {} +

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
