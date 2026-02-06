#!/bin/bash
set -e

# build_amd64_and_push.sh - Build and push AMD64 images to GHCR
export PATH=/usr/local/bin:/opt/homebrew/bin:/opt/podman/bin:$PATH

VERSION=$(cat VERSION)
echo "========================================"
echo "🏗️  BUILDING AMD64 IMAGES FOR v$VERSION 🏗️"
echo "========================================"

# Force AMD64 platform
export PLATFORM="linux/amd64"

echo "1. Building Proxy (AMD64)..."
docker build --platform $PLATFORM -t "ghcr.io/mavrovde/mavrov.de-proxy:$VERSION" -t "ghcr.io/mavrovde/mavrov.de-proxy:latest" ./proxy

echo "2. Building Backend (AMD64)..."
docker build --platform $PLATFORM -t "ghcr.io/mavrovde/mavrov.de-backend:$VERSION" -t "ghcr.io/mavrovde/mavrov.de-backend:latest" ./backend

echo "3. Building Frontend (AMD64)..."
docker build --platform $PLATFORM -t "ghcr.io/mavrovde/mavrov.de-frontend:$VERSION" -t "ghcr.io/mavrovde/mavrov.de-frontend:latest" ./frontend

echo ""
echo "========================================"
echo "🚀 PUSHING AMD64 IMAGES TO GHCR 🚀"
echo "========================================"

docker push "ghcr.io/mavrovde/mavrov.de-proxy:$VERSION"
docker push "ghcr.io/mavrovde/mavrov.de-proxy:latest"

docker push "ghcr.io/mavrovde/mavrov.de-backend:$VERSION"
docker push "ghcr.io/mavrovde/mavrov.de-backend:latest"

docker push "ghcr.io/mavrovde/mavrov.de-frontend:$VERSION"
docker push "ghcr.io/mavrovde/mavrov.de-frontend:latest"

echo "✅ AMD64 Images pushed successfully!"
