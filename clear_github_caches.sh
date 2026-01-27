#!/bin/bash
set -e

# clear_github_caches.sh
# Uses gh CLI to clear all GitHub Actions caches for the current repository.

if ! command -v gh &> /dev/null; then
    echo "Error: 'gh' CLI tool is not installed."
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "Error: 'jq' tool is not installed."
    exit 1
fi

# Get repo name (owner/repo)
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "🧹 Cleaning GitHub Actions caches for: $REPO"

# Loop until no caches remain
while true; do
    echo "Fetching cache list..."
    CACHES_JSON=$(gh api -H "Accept: application/vnd.github+json" \
                         -H "X-GitHub-Api-Version: 2022-11-28" \
                         "/repos/$REPO/actions/caches?per_page=100")

    # Extract IDs
    IDS=$(echo "$CACHES_JSON" | jq -r '.actions_caches[].id')

    if [ -z "$IDS" ] || [ "$IDS" == "null" ]; then
        echo "✅ No more caches found to delete."
        break
    fi

    COUNT=$(echo "$IDS" | wc -w | tr -d ' ')
    echo "found $COUNT caches in this batch."

    for ID in $IDS; do
        echo " - Deleting cache ID: $ID..."
        gh api --method DELETE \
               -H "Accept: application/vnd.github+json" \
               -H "X-GitHub-Api-Version: 2022-11-28" \
               "/repos/$REPO/actions/caches/$ID"
    done
done

echo "✨ All caches cleared!"
