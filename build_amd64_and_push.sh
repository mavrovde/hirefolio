#!/bin/bash
# build_amd64_and_push.sh — MANUAL FALLBACK: build + push AMD64 images from this machine.
#
# NOTE: CI is the primary publisher. On every push to main, deploy.yml builds the
# amd64 images and publishes them to ghcr.io (ghcr.io/mavrovde/hirefolio-* with
# sha-<gitsha> tags, anonymously pullable) and promotes them with version/latest
# tags — see .github/workflows/deploy.yml. Use this script only when a manual
# out-of-band publish is needed.
#
# Push target (defaults to ghcr.io — Docker Hub is NOT used):
#   REGISTRY     registry host (default: ghcr.io)
#   IMAGE_REPO   full repo base incl. registry host
#                (default: $REGISTRY/mavrovde/hirefolio; set explicitly for forks)
#
# You must already be logged in to the target registry
# (e.g. `gh auth token | docker login ghcr.io -u <user> --password-stdin`).
set -euo pipefail

export PATH=/usr/local/bin:/opt/homebrew/bin:$PATH

# Resolve the push target.
REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_REPO="${IMAGE_REPO:-$REGISTRY/mavrovde/hirefolio}"

# Read version from the latest git tag (authoritative source from release script)
GIT_TAG=$(git describe --tags --abbrev=0 2>/dev/null || true)
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
echo "    Target repo: $IMAGE_REPO-*"
echo "========================================"

# Force AMD64 platform
PLATFORM="linux/amd64"

# Build + push one component: $1 = component name, $2 = build context, $3 = optional Dockerfile
build_and_push() {
    local component=$1 context=$2 dockerfile=${3:-}
    local image="$IMAGE_REPO-$component"
    echo ""
    echo "🏗️  Building $component (AMD64) -> $image:$VERSION ..."
    if [ -n "$dockerfile" ]; then
        docker build --platform "$PLATFORM" -f "$dockerfile" -t "$image:$VERSION" -t "$image:latest" "$context"
    else
        docker build --platform "$PLATFORM" -t "$image:$VERSION" -t "$image:latest" "$context"
    fi
    echo "   Pushing $component..."
    docker push "$image:$VERSION"
    docker push "$image:latest"
}

build_and_push "backend" ./backend
build_and_push "frontend" ./frontend
build_and_push "admin-frontend" ./frontend ./frontend/Dockerfile.admin
build_and_push "proxy" ./proxy

echo ""
echo "✅ AMD64 images built and pushed to $IMAGE_REPO-* successfully!"
