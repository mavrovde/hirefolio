#!/bin/bash
set -e

# release.sh - Orchestrate a verified release process

echo "========================================"
echo "🚀 STARTING AUTOMATED RELEASE PROCESS 🚀"
echo "========================================"

# 1. Version Bump Type
BUMP_TYPE=$1
if [[ "$BUMP_TYPE" != "--patch" && "$BUMP_TYPE" != "--minor" && "$BUMP_TYPE" != "--major" ]]; then
    echo "Usage: ./release.sh [--patch|--minor|--major] [message]"
    exit 1
fi

# 2. Informative Message
DESC=$2
if [ -z "$DESC" ]; then
    echo "Please enter an informative commit message for this release:"
    read -r DESC
fi

if [ -z "$DESC" ]; then
    echo "❌ Error: Release message cannot be empty."
    exit 1
fi

# 3. Bump Version
echo "Step 1: Bumping version ($BUMP_TYPE)..."
./bump_version.sh "$BUMP_TYPE"
VERSION=$(cat VERSION)
export IMAGE_TAG="$VERSION"
echo "Target Version: v$VERSION"

# 4. Run Full Verification Suite
echo ""
echo "Step 2: Running mandatory verification suite..."
if ./verify_all.sh; then
    echo "✅ Verification PASSED."
else
    echo "❌ Verification FAILED. Release aborted."
    echo "Fix the issues and try again."
    exit 1
fi

echo ""
echo "Step 2b: Running Proxy Smoke Test (Prod Env)..."
if ./verify_proxy_startup.sh; then
    echo "✅ Proxy Smoke Test PASSED."
else
    echo "❌ Proxy Smoke Test FAILED. Release aborted."
    exit 1
fi

# 5. Commit synchronized version files
echo ""
echo "Step 3: Committing version updates..."
git add .
git commit -m "$DESC"

# 4. Git Tagging
echo ""
echo "Step 4: Tagging and pushing..."
git tag -a "v$VERSION" -m "$DESC"
git push origin main
git push origin "v$VERSION"

echo ""
echo "========================================"
echo "🎊 RELEASE v$VERSION SUCCESSFUL! 🎊"
echo "========================================"
