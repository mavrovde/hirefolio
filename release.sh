#!/bin/bash
set -euo pipefail

# release.sh - Orchestrate a verified release process

# Ensure docker is in PATH
export PATH=/usr/local/bin:/opt/homebrew/bin:$PATH

# Ensure npm is in PATH via NVM
export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

echo "========================================"
echo "🚀 STARTING AUTOMATED RELEASE PROCESS 🚀"
echo "========================================"
# Load environment variables from .env (sourced, so quoted values survive)
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
    echo "✅ Loaded environment variables from .env"
fi
# Ensure DOCKER_HOST is set for Podman (no-op when podman is not installed)
if [ -z "${DOCKER_HOST:-}" ] && command -v podman >/dev/null 2>&1; then
    PODMAN_SOCKET=$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}' 2>/dev/null || true)
    if [ -n "$PODMAN_SOCKET" ]; then
        export DOCKER_HOST="unix://$PODMAN_SOCKET"
        echo "✅ Set DOCKER_HOST to Podman socket: $DOCKER_HOST"
    fi
fi


# 1. Version Bump Type
BUMP_TYPE=${1:-}
if [[ "$BUMP_TYPE" != "--patch" && "$BUMP_TYPE" != "--minor" && "$BUMP_TYPE" != "--major" ]]; then
    echo "Usage: ./release.sh [--patch|--minor|--major] [message]"
    exit 1
fi

# 2. Informative Message
DESC=${2:-}
if [ -z "$DESC" ]; then
    echo "Please enter an informative commit message for this release:"
    read -r DESC
fi

if [ -z "$DESC" ]; then
    echo "❌ Error: Release message cannot be empty."
    exit 1
fi

# 3. Bump Version — updates ALL version carriers, including
# docker-compose.prod.yml image-tag defaults and
# frontend/projects/shared/package.json (#172).
echo "Step 1: Bumping version ($BUMP_TYPE)..."
./bump_version.sh "$BUMP_TYPE"
VERSION=$(tr -d '[:space:]' < VERSION)
export IMAGE_TAG="$VERSION"
echo "Target Version: v$VERSION"

# 3b. Sanity check: every version carrier must agree before we verify/tag.
./bump_version.sh --check



# 4. Run Full Verification Suite
echo ""
echo "Step 2: Running mandatory verification suite..."
if ./verify_all.sh; then
    echo "✅ Verification PASSED."
else
    echo "❌ Verification FAILED. Release aborted."
    echo "Reverting version bump..."
    git checkout -- VERSION backend/app/main.py frontend/package.json frontend/package-lock.json \
        frontend/projects/shared/package.json frontend/projects/public/src/app/version.ts \
        docker-compose.prod.yml CHANGELOG.md
    echo "Fix the issues and try again."
    exit 1
fi

echo ""
echo "Step 2b: Running Proxy Smoke Test (Prod Env)..."
if ./verify_proxy_startup.sh; then
    echo "✅ Proxy Smoke Test PASSED."
else
    echo "❌ Proxy Smoke Test FAILED. Release aborted."
    echo "Reverting version bump..."
    git checkout -- VERSION backend/app/main.py frontend/package.json frontend/package-lock.json \
        frontend/projects/shared/package.json frontend/projects/public/src/app/version.ts \
        docker-compose.prod.yml CHANGELOG.md
    exit 1
fi

# 5. Commit synchronized version files
echo ""
echo "Step 3: Committing version updates..."
git add .
# Prepend version to commit message for clarity
FINAL_MSG="v$VERSION: $DESC"
git commit -m "$FINAL_MSG"

# 4. Git Tagging
echo ""
echo "Step 4: Tagging and pushing code..."
git tag -a "v$VERSION" -m "$DESC"
git push origin main
git push origin "v$VERSION"

# 5. Build and Push AMD64 images
echo ""
echo "Step 5: Building and pushing AMD64 images..."
./build_amd64_and_push.sh

# Step 6 (Final Happy Path E2E) removed - redundant with Step 2's full 67-test E2E suite
# which already covers auth, AI suggestions, and admin features.

echo ""
echo "========================================"
echo "🎊 RELEASE v$VERSION SUCCESSFUL! 🎊"
echo "========================================"
