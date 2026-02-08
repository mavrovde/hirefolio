#!/bin/bash
set -e

# build_amd64_and_push.sh - Build and push AMD64 images to GHCR sequentially to save disk space
export PATH=/usr/local/bin:/opt/homebrew/bin:/opt/podman/bin:$PATH

VERSION=$(cat VERSION)
echo "========================================"
echo "🏗️  BUILDING AMD64 IMAGES FOR v$VERSION 🏗️"
echo "========================================"

# Force AMD64 platform
export PLATFORM="linux/amd64"

# 1. Backend
echo "1. Building Backend (AMD64)..."
docker build --platform $PLATFORM -t "maverickde/mavrov.de-backend:v$VERSION" -t "maverickde/mavrov.de-backend:latest" ./backend
echo "   Pushing Backend..."
podman push "maverickde/mavrov.de-backend:v$VERSION"
podman push "maverickde/mavrov.de-backend:latest"
echo "   Cleaning up local Backend images..."
# # docker rmi "maverickde/mavrov.de-backend:v$VERSION" "maverickde/mavrov.de-backend:latest" || true
# # docker system prune -f || true

# 2. Frontend
echo "2. Building Frontend (AMD64)..."
docker build --platform $PLATFORM -t "maverickde/mavrov.de-frontend:v$VERSION" -t "maverickde/mavrov.de-frontend:latest" ./frontend
echo "   Pushing Frontend..."
podman push "maverickde/mavrov.de-frontend:v$VERSION"
podman push "maverickde/mavrov.de-frontend:latest"
echo "   Cleaning up local Frontend images..."
## docker rmi "maverickde/mavrov.de-frontend:v$VERSION" "maverickde/mavrov.de-frontend:latest" || true
## docker system prune -f || true

# 3. Proxy
echo "3. Building Proxy (AMD64)..."
docker build --platform $PLATFORM -t "maverickde/mavrov.de-proxy:v$VERSION" -t "maverickde/mavrov.de-proxy:latest" ./proxy
echo "   Pushing Proxy..."
podman push "maverickde/mavrov.de-proxy:v$VERSION"
podman push "maverickde/mavrov.de-proxy:latest"
echo "   Cleaning up local Proxy images..."
# # docker rmi "maverickde/mavrov.de-proxy:v$VERSION" "maverickde/mavrov.de-proxy:latest" || true
# # docker system prune -f || true

echo "✅ AMD64 Images built, pushed, and cleaned up successfully!"
