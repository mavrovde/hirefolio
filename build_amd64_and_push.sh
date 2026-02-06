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
docker build --platform $PLATFORM -t "ghcr.io/mavrovde/mavrov.de-backend:$VERSION" -t "ghcr.io/mavrovde/mavrov.de-backend:latest" ./backend
echo "   Pushing Backend..."
docker push "ghcr.io/mavrovde/mavrov.de-backend:$VERSION"
docker push "ghcr.io/mavrovde/mavrov.de-backend:latest"
echo "   Cleaning up local Backend images..."
docker rmi "ghcr.io/mavrovde/mavrov.de-backend:$VERSION" "ghcr.io/mavrovde/mavrov.de-backend:latest"
docker system prune -f

# 2. Frontend
echo "2. Building Frontend (AMD64)..."
docker build --platform $PLATFORM -t "ghcr.io/mavrovde/mavrov.de-frontend:$VERSION" -t "ghcr.io/mavrovde/mavrov.de-frontend:latest" ./frontend
echo "   Pushing Frontend..."
docker push "ghcr.io/mavrovde/mavrov.de-frontend:$VERSION"
docker push "ghcr.io/mavrovde/mavrov.de-frontend:latest"
echo "   Cleaning up local Frontend images..."
docker rmi "ghcr.io/mavrovde/mavrov.de-frontend:$VERSION" "ghcr.io/mavrovde/mavrov.de-frontend:latest"
docker system prune -f

# 3. Proxy
echo "3. Building Proxy (AMD64)..."
docker build --platform $PLATFORM -t "ghcr.io/mavrovde/mavrov.de-proxy:$VERSION" -t "ghcr.io/mavrovde/mavrov.de-proxy:latest" ./proxy
echo "   Pushing Proxy..."
docker push "ghcr.io/mavrovde/mavrov.de-proxy:$VERSION"
docker push "ghcr.io/mavrovde/mavrov.de-proxy:latest"
echo "   Cleaning up local Proxy images..."
docker rmi "ghcr.io/mavrovde/mavrov.de-proxy:$VERSION" "ghcr.io/mavrovde/mavrov.de-proxy:latest"
docker system prune -f

echo "✅ AMD64 Images built, pushed, and cleaned up successfully!"
