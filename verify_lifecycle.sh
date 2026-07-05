#!/bin/bash
set -e

BASE_URL="http://localhost:8000/api"
USERNAME="admin"
PASSWORD="${ADMIN_PASSWORD:-}"

if [ -z "$PASSWORD" ]; then
  echo "ERROR: ADMIN_PASSWORD environment variable is not set."
  exit 1
fi

echo "1. Authenticating..."
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$USERNAME&password=$PASSWORD" | jq -r .access_token)

if [ "$TOKEN" == "null" ]; then
  echo "Auth failed"
  exit 1
fi
echo "Auth Token: ${TOKEN:0:10}..."

echo "2. Creating Post..."
SLUG="api-lifecycle-test"
curl -s -X POST "$BASE_URL/posts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "API Lifecycle Test",
    "slug": "'"$SLUG"'",
    "content": "Initial Content",
    "published": true,
    "language": "en",
    "tags": ["test-tag-1", "test-tag-2"]
  }' > create_response.json

CREATED_SLUG=$(jq -r .slug create_response.json)
CREATED_TAGS=$(jq -r '.tags | join(",")' create_response.json)

if [ "$CREATED_SLUG" != "$SLUG" ]; then
  echo "Creation failed: $(cat create_response.json)"
  exit 1
fi
if [[ "$CREATED_TAGS" != *"test-tag-1"* ]]; then
  echo "Tags failed in creation: $CREATED_TAGS"
  exit 1
fi
echo "Post Created with Tags: $CREATED_TAGS"

echo "3. Updating Post..."
curl -s -X PUT "$BASE_URL/posts/$SLUG" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "API Lifecycle UPDATED",
    "content": "Updated Content",
    "tags": ["test-tag-1", "updated-tag"]
  }' > update_response.json

UPDATED_TITLE=$(jq -r .title update_response.json)
UPDATED_TAGS=$(jq -r '.tags | join(",")' update_response.json)

if [ "$UPDATED_TITLE" != "API Lifecycle UPDATED" ]; then
  echo "Update failed: $(cat update_response.json)"
  exit 1
fi
if [[ "$UPDATED_TAGS" != *"updated-tag"* ]]; then
  echo "Tags Update failed: $UPDATED_TAGS"
  exit 1
fi
echo "Post Updated with Tags: $UPDATED_TAGS"

echo "4. Deleting Post..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/posts/$SLUG" \
  -H "Authorization: Bearer $TOKEN")

if [ "$HTTP_CODE" != "200" ]; then
  echo "Delete failed with code $HTTP_CODE"
  exit 1
fi
echo "Post Deleted."

echo "SUCCESS: Full CRUD Lifecycle Verified!"
