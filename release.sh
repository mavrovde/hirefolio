#!/bin/bash
set -e

# release.sh - Orchestrate a verified release process

echo "========================================"
echo "🚀 STARTING AUTOMATED RELEASE PROCESS 🚀"
echo "========================================"

# 1. Bump Version
echo "Step 1: Bumping version..."
./bump_version.sh
VERSION=$(cat VERSION)
echo "Target Version: v$VERSION"

# 2. Run Full Verification Suite
echo ""
echo "Step 2: Running mandatory verification suite..."
if ./verify_all.sh; then
    echo "✅ Verification PASSED."
else
    echo "❌ Verification FAILED. Release aborted."
    echo "Fix the issues and try again."
    exit 1
fi

# 3. Commit synchronized version files
echo ""
echo "Step 3: Committing version updates..."
DESC="Release v$VERSION: SSL Enabled (Certbot Sidecar), Enforce Audit, Final Cleanup."
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
