#!/bin/bash

# Read current version
current_version=$(cat VERSION)
IFS='.' read -r major minor patch <<< "$current_version"

# Increment patch
new_patch=$((patch + 1))
new_version="$major.$minor.$new_patch"

echo "Bumping version: $current_version -> $new_version"

# Update VERSION file
echo "$new_version" > VERSION

# Update backend/app/main.py
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/version=\"$current_version\"/version=\"$new_version\"/" backend/app/main.py
else
  sed -i "s/version=\"$current_version\"/version=\"$new_version\"/" backend/app/main.py
fi

# Update package.json
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/\"version\": \"$current_version\"/\"version\": \"$new_version\"/" frontend/package.json
else
  sed -i "s/\"version\": \"$current_version\"/\"version\": \"$new_version\"/" frontend/package.json
fi

# Update .env IMAGE_TAG using REGEX to handle desync
# Matches IMAGE_TAG=... and replaces with IMAGE_TAG=new_version
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/^IMAGE_TAG=.*/IMAGE_TAG=$new_version/" .env
else
  sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$new_version/" .env
fi

echo "Version updated to $new_version"
