#!/bin/bash

# Read current version
current_version=$(cat VERSION)
IFS='.' read -r major minor patch <<< "$current_version"

# Handle arguments
BUMP_TYPE=$1
if [ -z "$BUMP_TYPE" ]; then
    BUMP_TYPE="--patch"
fi

# Increment based on type
if [[ "$BUMP_TYPE" == "--major" ]]; then
    new_major=$((major + 1))
    new_version="$new_major.0.0"
elif [[ "$BUMP_TYPE" == "--minor" ]]; then
    new_minor=$((minor + 1))
    new_version="$major.$new_minor.0"
else
    new_patch=$((patch + 1))
    new_version="$major.$minor.$new_patch"
fi

echo "Bumping version ($BUMP_TYPE): $current_version -> $new_version"

# Update VERSION file
echo "$new_version" > VERSION

# Update backend/app/main.py
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/version=\"[0-9.]*\"/version=\"$new_version\"/" backend/app/main.py
else
  sed -i "s/version=\"[0-9.]*\"/version=\"$new_version\"/" backend/app/main.py
fi

# Update package.json
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/\"version\": \"[0-9.]*\"/\"version\": \"$new_version\"/" frontend/package.json
else
  sed -i "s/\"version\": \"[0-9.]*\"/\"version\": \"$new_version\"/" frontend/package.json
fi

# Update frontend/src/app/version.ts
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/VERSION = '.*';/VERSION = '$new_version';/" frontend/src/app/version.ts
else
  sed -i "s/VERSION = '.*';/VERSION = '$new_version';/" frontend/src/app/version.ts
fi

# Update .env IMAGE_TAG
if [ -f .env ]; then
  if grep -q "^IMAGE_TAG=" .env; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i '' "s/^IMAGE_TAG=.*/IMAGE_TAG=$new_version/" .env
    else
      sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$new_version/" .env
    fi
  else
    echo "IMAGE_TAG=$new_version" >> .env
  fi
else
  echo "IMAGE_TAG=$new_version" > .env
fi

# Sync package-lock.json with updated package.json
echo "Syncing frontend/package-lock.json..."
(cd frontend && npm install --package-lock-only --legacy-peer-deps > /dev/null 2>&1)
echo "package-lock.json synced."

# Git operations
if [ -d .git ]; then
    echo "Creating git tag v$new_version..."
    # We don't commit here as manage.sh or the user might want to include other changes
    # But we can provide a reminder or optionally tag the current commit
    # For now, let's just output the status. Tagging usually happens after the release commit.
fi

echo "Version updated to $new_version"
echo "Version updated to $new_version"
echo "Ready for verification and tagging."
