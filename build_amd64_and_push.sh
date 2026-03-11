#!/bin/bash
set -e

# build_amd64_and_push.sh - Build and push AMD64 images to GHCR sequentially to save disk space
export PATH=/usr/local/bin:/opt/homebrew/bin:/opt/podman/bin:$PATH

# Read version from the latest git tag (authoritative source from release script)
GIT_TAG=$(git describe --tags --abbrev=0 2>/dev/null)
if [ -z "$GIT_TAG" ]; then
  echo "❌ ERROR: No git tag found. Run the release script first."
  exit 1
fi
VERSION="${GIT_TAG#v}"  # Strip leading 'v' (e.g. v1.1.30 -> 1.1.30)

# Safety check: verify docker-compose.prod.yml matches this version
if ! grep -q "${VERSION}" docker-compose.prod.yml; then
  echo "❌ ERROR: docker-compose.prod.yml does not reference ${VERSION}. Version mismatch!"
  exit 1
fi

echo "========================================"
echo "🏗️  BUILDING AMD64 IMAGES FOR v$VERSION 🏗️"
echo "========================================"

# Force AMD64 platform
export PLATFORM="linux/amd64"

# 1. Backend
echo "1. Building Backend (AMD64)..."
docker build --platform $PLATFORM -t "maverickde/mavrov.de-backend:$VERSION" -t "maverickde/mavrov.de-backend:latest" ./backend
echo "   Pushing Backend..."
podman push "maverickde/mavrov.de-backend:$VERSION"
podman push "maverickde/mavrov.de-backend:latest"
echo "   Cleaning up local Backend images..."
# # docker rmi "maverickde/mavrov.de-backend:v$VERSION" "maverickde/mavrov.de-backend:latest" || true
# # docker system prune -f || true

# 2. Frontend
echo "2. Building Frontend (AMD64)..."
docker build --platform $PLATFORM -t "maverickde/mavrov.de-frontend:$VERSION" -t "maverickde/mavrov.de-frontend:latest" ./frontend
echo "   Pushing Frontend..."
podman push "maverickde/mavrov.de-frontend:$VERSION"
podman push "maverickde/mavrov.de-frontend:latest"
echo "   Cleaning up local Frontend images..."
## docker rmi "maverickde/mavrov.de-frontend:v$VERSION" "maverickde/mavrov.de-frontend:latest" || true
## docker system prune -f || true

# 3. Proxy
echo "3. Building Proxy (AMD64)..."
docker build --platform $PLATFORM -t "maverickde/mavrov.de-proxy:$VERSION" -t "maverickde/mavrov.de-proxy:latest" ./proxy
echo "   Pushing Proxy..."
podman push "maverickde/mavrov.de-proxy:$VERSION"
podman push "maverickde/mavrov.de-proxy:latest"
echo "   Cleaning up local Proxy images..."
# # docker rmi "maverickde/mavrov.de-proxy:v$VERSION" "maverickde/mavrov.de-proxy:latest" || true
# # docker system prune -f || true

echo "✅ AMD64 Images built, pushed, and cleaned up successfully!"
