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
# linkedin-api PyPI wheel has broken entry point (lint = black:None).
# Force source distribution install for linkedin-api, then install the rest normally.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-binary linkedin-api linkedin-api==2.2.1 && \
    pip install -r requirements.txt

# Final runtime stage inherits from base
FROM base AS runtime

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
